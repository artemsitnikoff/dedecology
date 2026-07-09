"""MAX bot wiring: bot factory, attachment helpers and the message handlers.

The handlers are the only business entrypoints:

* `/start` and greeting/empty messages get an EXAMPLE photo + caption that shows
  the exact address/time format we expect.
* A valid report MUST carry BOTH a photo AND text with a time «Время ЧЧ:ММ».
  When valid, the address (text before the time) and photo are forwarded to the
  backend intake API; otherwise the user gets a "wrong format" hint.

Every failure is caught, logged and turned into a soft reply so the long-polling
loop never dies.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import httpx
from maxapi import Bot, Router
from maxapi.client.default import DefaultConnectionProperties
from maxapi.enums.attachment import AttachmentType
from maxapi.enums.intent import Intent
from maxapi.enums.parse_mode import ParseMode
from maxapi.enums.sender_action import SenderAction
from maxapi.types import (
    CallbackButton,
    CommandStart,
    InputMediaBuffer,
    MessageCallback,
    MessageCreated,
)
from maxapi.types.attachments.image import Image
from maxapi.types.message import Message
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from .config import settings
from .errors import AppError, IntakeError
from .intake_client import (
    fetch_incident_types,
    fetch_map,
    finalize_max,
    prepare_max,
    push_incident,
)
from .session import (
    NO_MNO,
    PendingReport,
    PendingStore,
    button_text,
    chat_key,
    decode_payload,
    decode_type_payload,
    encode_payload,
    encode_type_payload,
    human_distance,
    map_query,
    merge_parsed,
    new_pending_id,
)

logger = logging.getLogger("dedecology.maxbot")

# Процессное хранилище отложенных обращений лички (создаётся ПОСЛЕ выбора МНО).
# Один long-polling процесс на бота → одного стора достаточно (см. session.py).
_STORE = PendingStore()

_DOWNLOAD_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Точный пример подписи БЕЗ опционального района — используется как образец в UI.
EXAMPLE = (
    "Московская область, г. Голицыно, ул. Советская д.56/2 "
    "напротив подъезда 2. Время 19:30"
)

# Время на фото: «Время 19:30», «время 9.05» и т.п. Группы: часы и минуты.
_TIME_RE = re.compile(r"врем[яи][\s:]*([0-2]?\d)[:.]([0-5]\d)", re.IGNORECASE)
# Любое время ЧЧ:ММ где угодно в тексте (со словом «Время» или без), для гибкого извлечения.
_ANY_TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")

# Приветствия/команды, на которые показываем пример (текст уже .strip()/.lower()).
_GREETINGS = {
    "привет",
    "здравствуйте",
    "start",
    "старт",
    "начать",
    "помощь",
    "/help",
    "hi",
    "hello",
}

# Бандл-ассет с примером фото: maxbot/assets/example.jpg (рядом с пакетом).
_EXAMPLE_IMAGE_PATH = Path(__file__).resolve().parent.parent / "assets" / "example.jpg"


def _read_example_image() -> bytes | None:
    """Прочитать байты примера один раз при импорте; None — если файла нет."""
    try:
        return _EXAMPLE_IMAGE_PATH.read_bytes()
    except OSError:
        logger.warning("example asset missing at %s — greeting will be text-only", _EXAMPLE_IMAGE_PATH)
        return None


_EXAMPLE_IMAGE_BYTES = _read_example_image()

_GREETING_CAPTION = (
    "Здравствуйте! Чтобы сообщить о площадке — пришлите ФОТО и подпись "
    "к нему в таком формате:\n\n" + EXAMPLE
)
_REPLY_INVALID_FORMAT = (
    "Неверный формат. Пришлите ФОТО площадки и подпись в формате:\n\n" + EXAMPLE
)
_REPLY_ACCEPTED = "Спасибо! Обращение принято и передано инспектору."
_REPLY_SOFT_ERROR = (
    "Не удалось обработать обращение прямо сейчас. Пожалуйста, попробуйте "
    "отправить его ещё раз чуть позже."
)

# --- тексты интерактивного флоу выбора МНО (только личка) ---
_ASK_ADDRESS = (
    "Не удалось определить адрес по описанию. Напишите, пожалуйста, адрес "
    "площадки одним сообщением: город, улица, дом."
)
_HDR_PICK = (
    "Нашёл ближайшие площадки накопления ТКО. Выберите, к какой относится "
    "обращение, либо «Нет в списке»:"
)
# Шаг 2 диалога — вопрос о типе инцидента (после выбора площадки).
_HDR_TYPE = "Площадка выбрана. Теперь выберите тип обращения:"
_TYPE_SKIP = "Пропустить"
# Потолок текста кнопки типа (в MAX Button.text ≤ 64; типы бывают длинными).
_TYPE_BUTTON_MAX = 60
_NO_MNO_NEARBY = (
    "Рядом (в радиусе 30 км) не нашёл известных площадок ТКО. Можно отправить "
    "обращение без привязки к площадке — инспектор разберётся."
)
_ADDR_UNRESOLVED = (
    "Адрес не распознал, но обращение принято по описанию — инспектор разберётся."
)
# Callback-ответы (кнопки).
_CB_EXPIRED = "Сессия истекла. Пришлите, пожалуйста, фото площадки заново."
_CB_ALREADY = "Это обращение уже отправлено."
_CB_PROCESSING = "Секунду, отправляю обращение…"
_CB_BAD_CHOICE = "Не удалось распознать выбор. Пришлите фото заново."
_CB_FINALIZE_FAIL = "Не удалось отправить обращение. Попробуйте ещё раз."


def create_bot() -> Bot:
    """Create a MAX bot that authenticates via the Authorization header.

    maxapi 0.9.4 only sends the token as `?access_token=…`; the MAX Bot API now
    returns 401 for query-string auth. We inject `Authorization: <token>` as a
    default header — maxapi forwards these kwargs into the aiohttp ClientSession,
    so the header rides on every request. See maxbot/maxapi_compat.py.
    """
    token = settings.MAX_BOT_TOKEN.get_secret_value()
    default_connection = DefaultConnectionProperties(
        headers={"Authorization": token},
    )
    return Bot(token=token, default_connection=default_connection)


def _all_images(msg: Message, limit: int = 3) -> list[Image]:
    """Return up to `limit` IMAGE attachments of the message (в сообщении Макса
    их может быть несколько — забираем все, как массив фоток в админке)."""
    if not msg.body or not msg.body.attachments:
        return []
    out: list[Image] = []
    for att in msg.body.attachments:
        if isinstance(att, Image) or getattr(att, "type", None) == AttachmentType.IMAGE:
            out.append(att)  # type: ignore[arg-type]
            if len(out) >= limit:
                break
    return out


def _sender_display_name(sender) -> str:
    """Build the display name: «Имя Фамилия» or the user_id as a string."""
    if sender is None:
        return ""
    first = (sender.first_name or "").strip()
    last = (sender.last_name or "").strip()
    return f"{first} {last}".strip() or str(sender.user_id)


def _is_greeting(text: str) -> bool:
    """True for an empty message or a known greeting/command word (case-insensitive)."""
    return not text or text.lower() in _GREETINGS


async def _download_image(image: Image, *, max_bytes: int) -> bytes:
    """Download image bytes from its signed payload URL (capped at max_bytes).

    MAX has no `bot.download()` — attachment content is served from a signed
    HTTPS URL on `attachment.payload.url`. We stream and enforce the size cap.
    """
    payload = getattr(image, "payload", None)
    url = getattr(payload, "url", None) if payload else None
    if not url:
        raise AppError(
            code="ATTACHMENT_NO_URL",
            message="У вложения нет URL для загрузки",
        )

    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise AppError(
                        code="ATTACHMENT_TOO_LARGE",
                        message=f"Вложение превышает {max_bytes} байт",
                    )
                chunks.append(chunk)
    return b"".join(chunks)


async def _send_example(msg: Message) -> None:
    """Reply with the EXAMPLE photo + caption; fall back to text if asset missing."""
    if _EXAMPLE_IMAGE_BYTES is None:
        await msg.answer(text=_GREETING_CAPTION)
        return
    photo = InputMediaBuffer(buffer=_EXAMPLE_IMAGE_BYTES, filename="example.jpg")
    await msg.answer(text=_GREETING_CAPTION, attachments=[photo])


def _extract_photo_time(text: str) -> str:
    """Время фотофиксации из текста: любое ЧЧ:ММ (напр. «…, 10:28» или «Время
    19:30»); иначе — текущее время приёма. Возврат — ISO "%Y-%m-%dT%H:%M"."""
    now = datetime.now()
    tm = _ANY_TIME_RE.search(text)
    if tm:
        return now.replace(
            hour=int(tm.group(1)), minute=int(tm.group(2)), second=0, microsecond=0
        ).strftime("%Y-%m-%dT%H:%M")
    return now.strftime("%Y-%m-%dT%H:%M")


async def _download_all(images: list[Image], mid) -> list[bytes]:
    """Скачать до 3 картинок; сбойную/слишком большую — молча пропустить."""
    photos: list[bytes] = []
    for img in images:
        try:
            photos.append(await _download_image(img, max_bytes=settings.MAX_PHOTO_BYTES))
        except AppError as exc:
            logger.warning("skip image mid=%s: %s", mid, exc.code)
    return photos


_ACK_UPLOADING = (
    "⏳ Загружаем фотографию… Некоторые фото весят много — это может занять несколько секунд."
)


async def _ack_uploading(event: MessageCreated, msg: Message, chat_id) -> None:
    """Мгновенная реакция на присланное фото: индикатор «крутилки» + текст.

    Шлём ДО тяжёлых download/parse (фото может весить мегабайты, разбор адреса — секунды),
    чтобы пользователь сразу видел активность и не думал, что бот завис. Индикатор
    SENDING_PHOTO Макс показывает как «крутилку» отправки. Всё best-effort — сбой
    уведомления НЕ должен сорвать основной приём обращения."""
    bot = getattr(event, "bot", None)
    if bot is not None and chat_id is not None:
        try:
            await bot.send_action(chat_id, SenderAction.SENDING_PHOTO)
        except Exception:  # noqa: BLE001
            logger.debug("send_action(sending_photo) failed", exc_info=True)
    try:
        await msg.answer(text=_ACK_UPLOADING)
    except Exception:  # noqa: BLE001
        logger.debug("ack uploading answer failed", exc_info=True)


def _point_of(prep: dict) -> tuple[float, float] | None:
    """Достать (lat, lon) точки обращения из ответа /prepare; None — если нет."""
    pt = prep.get("point") if isinstance(prep, dict) else None
    if not isinstance(pt, dict):
        return None
    lat, lon = pt.get("lat"), pt.get("lon")
    if lat is None or lon is None:
        return None
    try:
        return (float(lat), float(lon))
    except (TypeError, ValueError):
        return None


def _quote_of(result) -> str:
    """Мотивирующая цитата из ответа finalize (может отсутствовать)."""
    if isinstance(result, dict):
        return (result.get("quote") or "").strip()
    return ""


def _candidate_line(i: int, c: dict) -> str:
    """Строка нумерованного списка кандидатов (HTML-разметка).

    Жирным — «i. <реестровый №>» (напр. «1. 78-06-002210»), дальше НЕ жирным адрес и
    расстояние. Нет реестрового № → жирным «i.» + название. Динамику (reg/имя/адрес)
    экранируем — идёт с parse_mode=HTML."""
    reg = (c.get("reg") or "").strip()
    name = (c.get("name") or "").strip()
    addr = (c.get("address") or "").strip()
    dist = human_distance(c.get("distance_m"))
    bold = f"{i}. {html.escape(reg)}" if reg else f"{i}."
    line = f"<b>{bold}</b>"
    tail: list[str] = []
    if not reg and name:
        tail.append(html.escape(name))
    if addr:
        tail.append(html.escape(addr))
    if tail:
        line += " — " + ", ".join(tail)
    if dist:
        line += f" ({dist})"
    return line


def _build_keyboard(pending_id: str, candidates: list[dict]):
    """Инлайн-клавиатура: по кнопке на кандидата + кнопка «без привязки».

    idx в payload — 0-based индекс в candidates (в callback берём candidates[idx]);
    номер в подписи — 1-based. Пустой список → одна кнопка «Отправить без привязки».
    """
    b = InlineKeyboardBuilder()
    for idx, c in enumerate(candidates):
        b.row(
            CallbackButton(
                text=button_text(idx + 1, c.get("reg", ""), c.get("name", "")),
                payload=encode_payload(pending_id, idx),
                intent=Intent.DEFAULT,
            )
        )
    if candidates:
        b.row(
            CallbackButton(
                text="Нет в списке",
                payload=encode_payload(pending_id, NO_MNO),
                intent=Intent.NEGATIVE,
            )
        )
    else:
        b.row(
            CallbackButton(
                text="Отправить без привязки",
                payload=encode_payload(pending_id, NO_MNO),
                intent=Intent.POSITIVE,
            )
        )
    # maxapi 0.9.4: билдер стартует с пустого ряда [[]] — отфильтровать пустые ряды.
    b.payload = [r for r in b.payload if r]
    return b.as_markup()


def _build_type_keyboard(pending_id: str, types: list[dict]):
    """Инлайн-клавиатура выбора типа инцидента (справочник incident_types) + «Пропустить».

    По кнопке на тип (payload «t:{pid}:{code}», подпись — label, обрезанная до
    _TYPE_BUTTON_MAX) и кнопка «Пропустить» (payload «t:{pid}:» — пустой код → без типа)."""
    b = InlineKeyboardBuilder()
    for t in types:
        code = str(t.get("code") or "")
        label = str(t.get("label") or code).strip() or code
        if not code:
            continue
        if len(label) > _TYPE_BUTTON_MAX:
            label = label[: _TYPE_BUTTON_MAX - 1].rstrip() + "…"
        b.row(
            CallbackButton(
                text=label,
                payload=encode_type_payload(pending_id, code),
                intent=Intent.DEFAULT,
            )
        )
    b.row(
        CallbackButton(
            text=_TYPE_SKIP,
            payload=encode_type_payload(pending_id, ""),
            intent=Intent.NEGATIVE,
        )
    )
    # maxapi 0.9.4: билдер стартует с пустого ряда [[]] — отфильтровать пустые ряды.
    b.payload = [r for r in b.payload if r]
    return b.as_markup()


def _type_label(types: list[dict], code: str) -> str:
    """Подпись типа по коду из сохранённого справочника; «» — если код пуст/не найден."""
    code = (code or "").strip()
    if not code:
        return ""
    for t in types or []:
        if str(t.get("code") or "") == code:
            return str(t.get("label") or "").strip()
    return ""


async def _send_report_prompt(
    msg: Message, report: PendingReport, point: tuple[float, float] | None
) -> None:
    """Показать карту + список кандидатов + инлайн-кнопки выбора (одно сообщение)."""
    candidates = report.candidates
    markup = _build_keyboard(report.pending_id, candidates)

    if candidates:
        # Пустая строка между пунктами — список читается легче (по просьбе с прода).
        body = "\n\n".join(
            _candidate_line(i + 1, c) for i, c in enumerate(candidates)
        )
        text = f"{_HDR_PICK}\n\n{body}"
        png = None
        if point is not None:
            png = await fetch_map(point[0], point[1], map_query(point, candidates))
        attachments = []
        if png:
            attachments.append(InputMediaBuffer(buffer=png, filename="map.png"))
        attachments.append(markup)
        # parse_mode=HTML — жирные номера/реестровые № в списке (_candidate_line).
        await msg.answer(
            text=text, attachments=attachments, parse_mode=ParseMode.HTML
        )
    else:
        # Кандидатов нет — карту не рисуем, только предложение отправить без привязки.
        await msg.answer(text=_NO_MNO_NEARBY, attachments=[markup])


async def _finalize(report: PendingReport, mno_id: str, incident_type: str = "") -> dict:
    """Создать обращение из полей pending + выбранного МНО (или без него) + типа."""
    p = report.parsed
    return await finalize_max(
        region=p.get("region", ""),
        city=p.get("city", ""),
        street=p.get("street", ""),
        coords=p.get("coords", ""),
        comment=p.get("comment", ""),
        photo_time=p.get("photo_time", ""),
        msg_id=report.msg_id,
        sender_name=report.sender_name,
        msg_url=report.msg_url,
        mno_id=mno_id,
        photo_bytes_list=report.photos,
        incident_type=incident_type,
    )


async def _start_report(
    msg: Message,
    *,
    text: str,
    photos: list[bytes],
    sender_name: str,
    msg_id: str,
    msg_url: str,
    chat_id,
    user_id,
) -> None:
    """DM: фото+текст → prepare → карта+кнопки (или просьба прислать адрес)."""
    photo_time = _extract_photo_time(text)
    # Справочник типов инцидента тянем ПАРАЛЛЕЛЬНО с разбором адреса — чтобы на тапе по
    # площадке (шаг 1) он уже был готов и клавиатура типов открывалась мгновенно, без
    # 3-4с сетевого запроса в колбэке (жалоба с прода). Сбой fetch → [] (деградация).
    types_task = asyncio.create_task(fetch_incident_types())
    try:
        prep = await prepare_max(text, photo_time=photo_time)  # IntakeError → внешний soft-reply
    except BaseException:
        types_task.cancel()
        raise
    try:
        prefetched_types = await types_task
    except Exception:  # noqa: BLE001
        prefetched_types = []
    report = PendingReport(
        pending_id=new_pending_id(),
        chat_id=chat_id,
        user_id=user_id,
        photos=photos,
        sender_name=sender_name,
        msg_url=msg_url,
        msg_id=msg_id,
        parsed=(prep.get("parsed") or {}),
        incident_types=prefetched_types,
    )
    if prep.get("status") == "need_address":
        report.awaiting_address = True
        _STORE.put(report)
        await msg.answer(text=_ASK_ADDRESS)
        return
    report.candidates = prep.get("candidates") or []
    _STORE.put(report)
    await _send_report_prompt(msg, report, _point_of(prep))


async def _handle_address_reply(msg: Message, report: PendingReport, address: str) -> None:
    """DM: пользователь прислал адрес текстом на просьбу уточнить.

    ok → показать карту+кнопки; снова need_address → принять обращение по
    описанию БЕЗ привязки (чтобы не потерять фото/описание)."""
    prep = await prepare_max(address, photo_time=report.parsed.get("photo_time", ""))
    # Новый разбор поверх исходного, НЕ затирая непустые comment/photo_time из подписи.
    report.parsed = merge_parsed(report.parsed, prep.get("parsed") or {})

    if prep.get("status") == "ok":
        report.candidates = prep.get("candidates") or []
        report.awaiting_address = False
        _STORE.put(report)
        await _send_report_prompt(msg, report, _point_of(prep))
        return

    # Адрес снова не распознан → принимаем по описанию, без привязки к МНО.
    report.awaiting_address = False
    try:
        result = await _finalize(report, mno_id="")
    except IntakeError:
        report.awaiting_address = True  # вернуть ожидание — пусть повторит
        _STORE.put(report)
        raise  # внешний обработчик ответит мягкой ошибкой
    report.finalized = True
    report.photos = []  # освободить память — байты фото больше не нужны
    _STORE.put(report)
    quote = _quote_of(result)
    reply = _ADDR_UNRESOLVED + (f"\n\n{quote}" if quote else "")
    await msg.answer(text=reply)


async def _handle_group_report(
    msg: Message, *, text: str, mid, sender_name: str, images: list[Image]
) -> None:
    """ГРУППА: прежний прямой приём (push_incident), БЕЗ интерактива с МНО."""
    if not (images and text):
        logger.info("ignored group message mid=%s (нет фото или пустой текст)", mid)
        return
    photos = await _download_all(images, mid)
    if not photos:
        logger.info("ignored group message mid=%s (нет пригодного фото)", mid)
        return
    photo_time = _extract_photo_time(text)
    msg_url = getattr(msg, "url", None) or ""
    logger.info(
        "max msg url=%r chat_id=%s seq=%s mid=%s",
        getattr(msg, "url", None),
        getattr(getattr(msg, "recipient", None), "chat_id", None),
        getattr(getattr(msg, "body", None), "seq", None),
        mid,
    )
    result = await push_incident(
        text=text,
        msg_id=str(mid),
        sender_name=sender_name,
        photo_bytes_list=photos,
        photo_time=photo_time,
        msg_url=msg_url,
    )
    quote = _quote_of(result)
    reply = _REPLY_ACCEPTED + (f"\n\n{quote}" if quote else "")
    await msg.answer(text=reply)


async def _notify_callback(event: MessageCallback, text: str) -> None:
    """Показать ТОЛЬКО тост-уведомление, НЕ трогая исходное сообщение (список +
    кнопки остаются как есть — важно для повторов/ошибок с возможностью retry).
    В отличие от event.answer, message=None → текст/вложения не переписываются."""
    bot = getattr(event, "bot", None)
    if bot is None:
        return
    await bot.send_callback(callback_id=event.callback.callback_id, notification=text)


async def _edit_callback_message(event: MessageCallback, text: str, markup=None) -> None:
    """Отредактировать сообщение с кнопками: заменить текст и вложения.

    markup=None → attachments НЕ передаём, edit_message шлёт `attachments: []` (см.
    исходник maxapi 0.9.4 EditMessage) → клавиатура и карта УБИРАЮТСЯ. markup задан →
    ставим новую клавиатуру (шаг 2: вопрос о типе). Зовём сразу по тапу, чтобы кнопки
    не оставались жать до ответа бэка. Бот/mid недоступны или edit не прошёл → фолбэк
    отдельным сообщением."""
    attachments = [markup] if markup is not None else None
    bot = getattr(event, "bot", None)
    body = getattr(getattr(event, "message", None), "body", None)
    mid = getattr(body, "mid", None)
    if bot is not None and mid:
        try:
            await bot.edit_message(
                message_id=mid,
                text=text,
                attachments=attachments,
                parse_mode=ParseMode.HTML,
            )
            return
        except Exception:  # noqa: BLE001 — не вышло отредактировать → фолбэк ниже
            logger.exception("edit_message не удалось mid=%s", mid)
    try:
        await event.message.answer(
            text=text, attachments=attachments, parse_mode=ParseMode.HTML
        )
    except Exception:  # noqa: BLE001
        logger.exception("edit fallback answer не удалось")


async def _do_finalize(
    event: MessageCallback,
    report: PendingReport,
    mno_id: str,
    incident_type: str,
    mno_label: str,
    is_no_mno: bool,
) -> None:
    """Финал обоих шагов: замок → «⏳» (снять клавиатуру) → finalize → подтверждение.

    Мгновенно гасит клавиатуру и показывает прогресс (finalize ≈ загрузка фото + цитата),
    ставит синхронный замок report.processing против двойного создания. Успех → «✅ Спасибо»
    с площадкой и типом; IntakeError → просьба прислать фото заново (обращение НЕ создано)."""
    report.processing = True
    await _notify_callback(event, "Принято ✅")
    await _edit_callback_message(event, "⏳ Отправляю обращение…")
    try:
        result = await _finalize(report, mno_id, incident_type)
    except IntakeError:
        report.processing = False
        await _edit_callback_message(
            event,
            "❌ Не удалось отправить. Пришлите, пожалуйста, фото площадки заново.",
        )
        return

    report.finalized = True
    report.processing = False
    report.photos = []  # освободить память (байты фото уже отправлены)
    _STORE.put(report)

    parts = ["✅ Спасибо! Обращение принято."]
    if mno_label:
        parts.append(f"Площадка: <b>{html.escape(mno_label)}</b>")
    elif is_no_mno:
        parts.append("Отправлено без привязки к площадке.")
    type_label = _type_label(report.incident_types, incident_type)
    if type_label:
        parts.append(f"Тип: <b>{html.escape(type_label)}</b>")
    quote = _quote_of(result)
    if quote:
        parts.append("")
        parts.append(html.escape(quote))
    await _edit_callback_message(event, "\n".join(parts))


def build_router() -> Router:
    """Build the router: a `/start` handler plus the main message handler."""
    router = Router()

    # ВАЖНО: /start регистрируем первым, чтобы команда не утекла в общий обработчик.
    @router.message_created(CommandStart())
    async def on_start(event: MessageCreated) -> None:
        msg = event.message
        try:
            await _send_example(msg)
        except Exception:  # noqa: BLE001 — poller must never die on one bad message
            logger.exception(
                "failed to handle /start mid=%s",
                getattr(getattr(msg, "body", None), "mid", None),
            )
            await _safe_reply(msg)

    @router.message_created()
    async def on_message_created(event: MessageCreated) -> None:
        msg = event.message
        # В ГРУППЕ бот не болтает: принимает только фото+подпись (прямой push_incident,
        # без интерактива с МНО). Приветствие/ошибки/не-фото в группе — молча.
        ct = getattr(getattr(msg, "recipient", None), "chat_type", None)
        is_group = getattr(ct, "value", ct) == "chat"
        try:
            body = msg.body
            text = ((body.text if body else None) or "").strip()
            mid = body.mid if body else ""
            sender_name = _sender_display_name(msg.sender)
            images = _all_images(msg)

            # --- ГРУППА: прежнее поведение без изменений ---
            if is_group:
                await _handle_group_report(
                    msg, text=text, mid=mid, sender_name=sender_name, images=images
                )
                return

            # --- ЛИЧКА: интерактивный флоу с отложенным созданием обращения ---
            chat_id = getattr(getattr(msg, "recipient", None), "chat_id", None)
            user_id = getattr(getattr(msg, "sender", None), "user_id", None)

            # 1) Ответ-адрес: текст без фото, а мы ждём адрес по этому чату.
            if not images and text:
                now = time.time()
                _STORE.purge(now)
                pending = _STORE.find_awaiting(chat_key(chat_id, user_id), now=now)
                if pending is not None and not _is_greeting(text):
                    await _handle_address_reply(msg, pending, text)
                    return

            # 2) Приветствие/пустое сообщение без фото → пример формата.
            if not images and _is_greeting(text):
                await _send_example(msg)
                return

            # 3) Новое обращение = ФОТО + непустой текст (адрес/описание).
            if images and text:
                # Мгновенно подтверждаем приём фото (крутилка + текст) ДО скачивания/разбора.
                await _ack_uploading(event, msg, chat_id)
                photos = await _download_all(images, mid)
                if photos:
                    msg_url = getattr(msg, "url", None) or ""
                    logger.info(
                        "max msg url=%r chat_id=%s seq=%s mid=%s",
                        getattr(msg, "url", None),
                        chat_id,
                        getattr(body, "seq", None),
                        mid,
                    )
                    await _start_report(
                        msg,
                        text=text,
                        photos=photos,
                        sender_name=sender_name,
                        msg_id=str(mid),
                        msg_url=msg_url,
                        chat_id=chat_id,
                        user_id=user_id,
                    )
                    return

            # Невалидно (нет фото / пустой текст) — молчим.
            logger.info("ignored message mid=%s (нет фото или пустой текст)", mid)

        except AppError as exc:
            logger.warning(
                "handler AppError code=%s msg=%s mid=%s",
                exc.code,
                exc.message,
                getattr(getattr(msg, "body", None), "mid", None),
            )
            await _safe_reply(msg)
        except Exception:  # noqa: BLE001 — poller must never die on one bad message
            logger.exception(
                "unexpected error handling message mid=%s",
                getattr(getattr(msg, "body", None), "mid", None),
            )
            await _safe_reply(msg)

    @router.message_callback()
    async def on_callback(event: MessageCallback) -> None:
        """Тап по кнопке. Двухшаговый диалог: шаг 1 — выбор площадки (→ спросить тип),
        шаг 2 — выбор типа инцидента (→ создать обращение).

        Клавиатуру после каждого шага меняем/убираем через edit_message (кнопки не
        «висят»), тост даёт мгновенную обратную связь. Против двойного создания —
        синхронный замок report.processing в _do_finalize. Повторный тап по уже
        отправленному/обрабатываемому → только тост.
        """
        try:
            payload = event.callback.payload or ""
            mno_dec = decode_payload(payload)  # (pid, idx) — шаг 1
            # Типовой payload разбираем только если это НЕ МНО-payload.
            type_dec = decode_type_payload(payload) if mno_dec is None else None
            if mno_dec is None and type_dec is None:
                await _notify_callback(event, _CB_BAD_CHOICE)
                return
            pid = mno_dec[0] if mno_dec is not None else type_dec[0]

            _STORE.purge(time.time())
            report = _STORE.get(pid)
            if report is None:
                await _notify_callback(event, _CB_EXPIRED)
                return
            if report.finalized:
                await _notify_callback(event, _CB_ALREADY)
                return
            if report.processing:
                await _notify_callback(event, _CB_PROCESSING)
                return

            # === Шаг 2: выбран тип инцидента → создаём обращение ===
            if type_dec is not None:
                _, code = type_dec
                mno_id = report.chosen_mno_id or ""
                await _do_finalize(
                    event, report, mno_id, code, report.chosen_mno_label, mno_id == ""
                )
                return

            # === Шаг 1: выбрана площадка → спрашиваем тип инцидента ===
            idx = mno_dec[1]
            if idx == NO_MNO:
                mno_id = ""
                mno_label = ""
            else:
                if not isinstance(idx, int) or idx >= len(report.candidates):
                    await _notify_callback(event, _CB_BAD_CHOICE)
                    return
                cand = report.candidates[idx]
                mno_id = str(cand.get("id") or "")
                # Подпись выбранной площадки — реестровый № (или название), как в списке.
                mno_label = (cand.get("reg") or "").strip() or (
                    cand.get("name") or ""
                ).strip()

            report.chosen_mno_id = mno_id
            report.chosen_mno_label = mno_label

            # Мгновенно: тост ДО любых сетевых вызовов — кнопки не «висят». Справочник
            # типов берём из ПРЕДЗАГРУЖЕННОГО на старте (report.incident_types); фолбэк на
            # fetch (кэш) — только если предзагрузка не сработала.
            await _notify_callback(event, "Площадка выбрана")
            types = report.incident_types or await fetch_incident_types()
            if types:
                report.incident_types = types
                report.awaiting_type = True
                _STORE.put(report)
                # Меняем сообщение на вопрос о типе + клавиатуру типов (карта/МНО-кнопки уходят).
                await _edit_callback_message(
                    event, _HDR_TYPE, markup=_build_type_keyboard(pid, types)
                )
                return

            # Справочник типов недоступен → создаём сразу без типа (деградация).
            await _do_finalize(event, report, mno_id, "", mno_label, idx == NO_MNO)

        except Exception:  # noqa: BLE001 — poller must never die on one bad callback
            logger.exception("unexpected error handling callback")
            try:
                await _notify_callback(event, _CB_FINALIZE_FAIL)
            except Exception:  # noqa: BLE001
                logger.exception("failed to send callback error notification")

    return router


async def _safe_reply(msg: Message) -> None:
    """Best-effort soft error reply; swallow secondary failures. В группе молчим."""
    ct = getattr(getattr(msg, "recipient", None), "chat_type", None)
    if getattr(ct, "value", ct) == "chat":
        return
    try:
        await msg.answer(text=_REPLY_SOFT_ERROR)
    except Exception:  # noqa: BLE001
        logger.exception("failed to send soft-error reply")
