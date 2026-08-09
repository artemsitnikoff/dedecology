"""Telegram-бот ЭкоПульс: диспетчер апдейтов + обработчики (зеркало maxbot/bot.py).

Поток (ЛИЧКА):
  * `/start`, приветствие/пустое → пример фото+подпись (assets/example.jpg);
  * ФОТО → ACK (sendChatAction + текст) → скачать фото → PendingReport(awaiting_location)
    → ReplyKeyboard с кнопкой «📍 Отправить геопозицию» + «или пришлите адрес текстом»;
  * location → prepare_coords(lat,lon) → снять reply-клавиатуру → карта + инлайн-список
    кандидатов → шаг ТИП → шаг ПОДТИП → finalize (source='telegram');
  * текст (когда ждём адрес) → prepare_max(text) (AI-фолбэк) → тот же выбор площадки;
  * callback_query — двухшаговый диалог (МНО → тип → подтип), 1:1 с maxbot (анти-дубль
    report.processing, тост answerCallbackQuery, снятие кнопок deleteMessage + новое
    сообщение).

Поток (ГРУППА): фото+подпись → прямой push_incident(source='telegram'), без интерактива.

Concurrency: main.py обрабатывает апдейты ПОСЛЕДОВАТЕЛЬНО (await dispatch по очереди —
как последовательный поллер maxapi у maxbot), поэтому два апдейта одной пачки НЕ бегут
конкурентно за общий PendingReport. Тяжёлое (скачивание фото, финализация) обработчики
уводят в фон через _spawn ПОСЛЕ синхронной установки замка (report.processing/awaiting_*):
поллер остаётся отзывчивым, а повторный тап/сообщение уже видит выставленный замок.
Каждый сбой ловится и логируется — поллер не умирает.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import time
from datetime import datetime
from pathlib import Path

from .config import settings
from .errors import AppError, IntakeError
from .intake_client import (
    fetch_incident_subtypes,
    fetch_incident_types,
    fetch_map,
    finalize_max,
    prepare_coords,
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
    decode_subtype_payload,
    decode_type_payload,
    encode_payload,
    encode_subtype_payload,
    encode_type_payload,
    human_distance,
    map_query,
    merge_parsed,
    new_pending_id,
)
from .tgapi import (
    TelegramAPI,
    display_name,
    extract_location,
    inline_keyboard,
    largest_photo_file_id,
    message_text,
    remove_reply_keyboard,
    reply_keyboard_location,
    update_kind,
)

logger = logging.getLogger("dedecology.telegrambot")

# Процессное хранилище отложенных обращений лички (создаётся ПОСЛЕ выбора МНО).
# Один long-polling процесс на бота → одного стора достаточно (см. session.py).
_STORE = PendingStore()


def _spawn(coro) -> None:
    """Запустить корутину в ФОНЕ (fire-and-forget), гася/логируя исключения.

    Тяжёлую/долгую работу (finalize с загрузкой фото, скачивание фото) уводим сюда ПОСЛЕ
    синхронной установки замка — чтобы последовательный поллер не блокировался на секундном
    (а то и до таймаута) сетевом вызове, но повторный апдейт уже видел выставленный замок."""

    async def _run() -> None:
        try:
            await coro
        except Exception:  # noqa: BLE001
            logger.exception("background task failed")

    asyncio.create_task(_run())


# Точный пример подписи БЕЗ опционального района — используется как образец в UI.
EXAMPLE = (
    "Московская область, г. Голицыно, ул. Советская д.56/2 "
    "напротив подъезда 2. Время 19:30"
)

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

# Гео-кнопка reply-клавиатуры (request_location; работает только в личке).
_GEO_BUTTON = "📍 Отправить геопозицию"

# Бандл-ассет с примером фото: telegrambot/assets/example.jpg (рядом с пакетом).
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
    "Здравствуйте! Чтобы сообщить о площадке — пришлите ФОТО площадки ТКО. "
    "Затем нажмите кнопку «📍 Отправить геопозицию» или пришлите адрес текстом "
    "(город, улица, дом). Пример подписи к фото:\n\n" + EXAMPLE
)
_REPLY_SOFT_ERROR = (
    "Не удалось обработать обращение прямо сейчас. Пожалуйста, попробуйте "
    "отправить его ещё раз чуть позже."
)
_REPLY_ACCEPTED = "Спасибо! Обращение принято и передано инспектору."

# --- тексты интерактивного флоу выбора МНО (только личка) ---
_ACK_UPLOADING = (
    "Фотография принята в обработку. Секунду…"
)
_ASK_LOCATION = (
    "Фото принято ✅\n\nТеперь отправьте геопозицию площадки кнопкой «📍 Отправить "
    "геопозицию» ниже — или пришлите адрес текстом (город, улица, дом)."
)
_LOC_ACCEPTED = "Геопозиция принята. Ищу ближайшие площадки…"
_ADDR_ACCEPTED = "Адрес принят. Ищу ближайшие площадки…"
_HDR_PICK = (
    "Нашёл ближайшие площадки накопления ТКО. Выберите, к какой относится "
    "обращение, либо «Нет в списке»:"
)
# Шаг 2 диалога — вопрос о типе инцидента (после выбора площадки).
_HDR_TYPE = "Площадка выбрана. Теперь выберите тип обращения:"
_TYPE_SKIP = "Пропустить"
# Шаг 3 — подтип (только для типа с подтипами, «Отсутствует доступ к МНО»). Обязателен.
_HDR_SUBTYPE = "Уточните подтип обращения:"
# Потолок текста кнопки типа (типы бывают длинными).
_TYPE_BUTTON_MAX = 60
_NO_MNO_NEARBY = (
    "Рядом (в радиусе 30 км) не нашёл известных площадок ТКО. Можно отправить "
    "обращение без привязки к площадке — инспектор разберётся."
)
_ADDR_UNRESOLVED = (
    "Адрес не распознал, но обращение принято по описанию — инспектор разберётся."
)
# Callback-ответы (тосты кнопок).
_CB_EXPIRED = "Сессия истекла. Пришлите, пожалуйста, фото площадки заново."
_CB_ALREADY = "Это обращение уже отправлено."
_CB_PROCESSING = "Секунду, отправляю обращение…"
_CB_BAD_CHOICE = "Не удалось распознать выбор. Пришлите фото заново."
_CB_FINALIZE_FAIL = "Не удалось отправить обращение. Попробуйте ещё раз."


# ---------------------------------------------------------------------------
# Мелкие чистые хелперы.
# ---------------------------------------------------------------------------

def _is_greeting(text: str) -> bool:
    """True для пустого сообщения, команды (начинается с «/») или слова-приветствия."""
    if not text:
        return True
    low = text.lower()
    return low in _GREETINGS or low.startswith("/")


def _extract_photo_time(text: str) -> str:
    """Время фотофиксации из текста: любое ЧЧ:ММ (напр. «…, 10:28» или «Время 19:30»);
    иначе — текущее время приёма. Возврат — ISO "%Y-%m-%dT%H:%M"."""
    now = datetime.now()
    tm = _ANY_TIME_RE.search(text or "")
    if tm:
        return now.replace(
            hour=int(tm.group(1)), minute=int(tm.group(2)), second=0, microsecond=0
        ).strftime("%Y-%m-%dT%H:%M")
    return now.strftime("%Y-%m-%dT%H:%M")


def _point_of(prep: dict) -> tuple[float, float] | None:
    """Достать (lat, lon) точки обращения из ответа /prepare(-coords); None — если нет."""
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
    расстояние. Нет реестрового № → жирным «i.» + название. Динамику экранируем —
    идёт с parse_mode=HTML."""
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


def _build_mno_keyboard(pending_id: str, candidates: list[dict]) -> dict:
    """Инлайн-клавиатура: по кнопке на кандидата + кнопка «без привязки».

    idx в payload — 0-based индекс в candidates; номер в подписи — 1-based. Пустой
    список → одна кнопка «Отправить без привязки»."""
    rows: list[list[tuple[str, str]]] = []
    for idx, c in enumerate(candidates):
        rows.append(
            [(button_text(idx + 1, c.get("reg", ""), c.get("name", "")), encode_payload(pending_id, idx))]
        )
    if candidates:
        rows.append([("Нет в списке", encode_payload(pending_id, NO_MNO))])
    else:
        rows.append([("Отправить без привязки", encode_payload(pending_id, NO_MNO))])
    return inline_keyboard(rows)


def _build_type_keyboard(pending_id: str, types: list[dict]) -> dict:
    """Инлайн-клавиатура выбора типа инцидента (справочник incident_types) + «Пропустить».

    По кнопке на тип (payload «t:{pid}:{code}», подпись — label, обрезанная до
    _TYPE_BUTTON_MAX) и кнопка «Пропустить» (payload «t:{pid}:» — пустой код → без типа)."""
    rows: list[list[tuple[str, str]]] = []
    for t in types:
        code = str(t.get("code") or "")
        label = str(t.get("label") or code).strip() or code
        if not code:
            continue
        if len(label) > _TYPE_BUTTON_MAX:
            label = label[: _TYPE_BUTTON_MAX - 1].rstrip() + "…"
        rows.append([(label, encode_type_payload(pending_id, code))])
    rows.append([(_TYPE_SKIP, encode_type_payload(pending_id, ""))])
    return inline_keyboard(rows)


def _type_label(types: list[dict], code: str) -> str:
    """Подпись типа по коду из сохранённого справочника; «» — если код пуст/не найден."""
    code = (code or "").strip()
    if not code:
        return ""
    for t in types or []:
        if str(t.get("code") or "") == code:
            return str(t.get("label") or "").strip()
    return ""


def _build_subtype_keyboard(pending_id: str, subtypes: list[dict]) -> dict:
    """Инлайн-клавиатура выбора ПОДТИПА (шаг 3). Кнопки «s:{pid}:{code}»; «Пропустить»
    НЕТ — подтип обязателен (тип «Отсутствует доступ к МНО» без подтипа не создаётся)."""
    rows: list[list[tuple[str, str]]] = []
    for s in subtypes:
        code = str(s.get("code") or "")
        label = str(s.get("label") or code).strip() or code
        if not code:
            continue
        if len(label) > _TYPE_BUTTON_MAX:
            label = label[: _TYPE_BUTTON_MAX - 1].rstrip() + "…"
        rows.append([(label, encode_subtype_payload(pending_id, code))])
    return inline_keyboard(rows)


def _subtype_label(subtypes: list[dict], code: str) -> str:
    """Подпись подтипа по коду из сохранённой карты подтипов; «» — если не найден."""
    code = (code or "").strip()
    if not code:
        return ""
    for s in subtypes or []:
        if str(s.get("code") or "") == code:
            return str(s.get("label") or "").strip()
    return ""


# ---------------------------------------------------------------------------
# Отправка примера / показ списка площадок.
# ---------------------------------------------------------------------------

async def _send_example(api: TelegramAPI, chat_id) -> None:
    """Ответить примером фото+подписи; фолбэк на текст, если ассет отсутствует.

    Всегда снимаем reply-клавиатуру (гео-кнопку): пример показываем, когда активной
    гео-сессии нет (приветствие/команда/протухшая сессия) — незачем оставлять висящую кнопку."""
    if _EXAMPLE_IMAGE_BYTES is None:
        await api.send_message(chat_id, _GREETING_CAPTION, reply_markup=remove_reply_keyboard())
        return
    sent = await api.send_photo(
        chat_id,
        _EXAMPLE_IMAGE_BYTES,
        caption=_GREETING_CAPTION,
        filename="example.jpg",
        reply_markup=remove_reply_keyboard(),
    )
    if sent is None:
        # sendPhoto не прошёл (напр. слишком большой ассет) — хотя бы текст.
        await api.send_message(chat_id, _GREETING_CAPTION, reply_markup=remove_reply_keyboard())


async def _send_report_prompt(
    api: TelegramAPI, report: PendingReport, point: tuple[float, float] | None
) -> None:
    """Показать карту (отдельным сообщением) + список кандидатов с инлайн-кнопками.

    Карту шлём ОТДЕЛЬНЫМ сообщением, кнопки — ТЕКСТОВЫМ (правки/удаление на тапе быстрее,
    чем возня с сообщением-картинкой). map_mid запоминаем — удалить карту при выборе площадки."""
    candidates = report.candidates
    if not candidates:
        # Кандидатов нет — карту не рисуем, только предложение отправить без привязки.
        await api.send_message(
            report.chat_id, _NO_MNO_NEARBY, reply_markup=_build_mno_keyboard(report.pending_id, [])
        )
        return

    # 1) Карта — отдельным сообщением (без кнопок). Не критична: сбой/таймаут → без карты.
    if point is not None:
        png = await fetch_map(point[0], point[1], map_query(point, candidates))
        if png:
            sent = await api.send_photo(report.chat_id, png, filename="map.png")
            if isinstance(sent, dict):
                report.map_mid = sent.get("message_id")

    # 2) Список + кнопки — ТЕКСТОВОЕ сообщение (пустая строка между пунктами для читаемости).
    body = "\n\n".join(_candidate_line(i + 1, c) for i, c in enumerate(candidates))
    text = f"{_HDR_PICK}\n\n{body}"
    await api.send_message(
        report.chat_id, text, reply_markup=_build_mno_keyboard(report.pending_id, candidates)
    )


async def _finalize(
    report: PendingReport,
    mno_id: str,
    incident_type: str = "",
    incident_subtype: str = "",
) -> dict:
    """Создать обращение из полей pending + выбранного МНО (или без него) + типа/подтипа."""
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
        incident_subtype=incident_subtype,
    )


# ---------------------------------------------------------------------------
# Личка: приём фото → ожидание гео/адреса → выбор площадки.
# ---------------------------------------------------------------------------

async def _download_photo(api: TelegramAPI, file_id: str) -> bytes | None:
    """Скачать фото Telegram по file_id (getFile → download), потолок MAX_PHOTO_BYTES."""
    if not file_id:
        return None
    return await api.download_by_file_id(file_id, max_bytes=settings.MAX_PHOTO_BYTES)


async def _process_new_report(
    api: TelegramAPI,
    *,
    chat_id,
    user_id,
    message_id,
    sender_name: str,
    file_id: str,
    photo_time: str,
) -> None:
    """ЛИЧКА (в ФОНЕ через _spawn): фото → скачать → PendingReport(awaiting_location) → гео-кнопка.

    Уводится в _spawn на уровне _on_message (тяжёлое скачивание не блокирует поллер), поэтому
    со СВОИМ try/except: исключение фоновой задачи иначе «утекло» бы мимо обработчика (мягкий
    ответ + лог). Справочники типов/подтипов подтягиваем сразу (best-effort) — чтобы шаг выбора
    типа открывался мгновенно."""
    try:
        photo = await _download_photo(api, file_id)
        if not photo:
            logger.info("no photo downloaded chat_id=%s message_id=%s", chat_id, message_id)
            await api.send_message(chat_id, _REPLY_SOFT_ERROR)
            return

        try:
            prefetched_types = await fetch_incident_types()
        except Exception:  # noqa: BLE001 — деградация: без типов
            prefetched_types = []
        try:
            prefetched_subtypes = await fetch_incident_subtypes()
        except Exception:  # noqa: BLE001 — деградация: без подтипов
            prefetched_subtypes = {}

        report = PendingReport(
            pending_id=new_pending_id(),
            chat_id=chat_id,
            user_id=user_id,
            photos=[photo],
            sender_name=sender_name,
            msg_url="",
            msg_id=str(message_id),
            # coords резолвится позже (по гео/адресу); photo_time из подписи сохраняем сразу.
            parsed={"photo_time": photo_time},
            incident_types=prefetched_types,
            incident_subtypes=prefetched_subtypes,
        )
        report.awaiting_location = True
        report.awaiting_address = True  # принимаем и адрес текстом (текстовый фолбэк)
        _STORE.put(report)
        await api.send_message(
            chat_id, _ASK_LOCATION, reply_markup=reply_keyboard_location(_GEO_BUTTON)
        )
    except (AppError, IntakeError):
        await _safe_reply(api, chat_id, False)
    except Exception:  # noqa: BLE001 — фоновая задача не должна падать «в никуда»
        logger.exception("bg _process_new_report failed chat_id=%s", chat_id)
        await _safe_reply(api, chat_id, False)


async def _handle_location(
    api: TelegramAPI, report: PendingReport, lat: float, lon: float
) -> None:
    """ЛИЧКА: пришла геопозиция → prepare_coords → снять клавиатуру → карта + выбор МНО."""
    prep = await prepare_coords(lat, lon, report.parsed.get("photo_time", ""))
    report.parsed = merge_parsed(report.parsed, prep.get("parsed") or {})
    report.candidates = prep.get("candidates") or []
    report.awaiting_location = False
    report.awaiting_address = False
    _STORE.put(report)
    # Снять reply-клавиатуру (гео-кнопку) отдельным сообщением.
    await api.send_message(report.chat_id, _LOC_ACCEPTED, reply_markup=remove_reply_keyboard())
    await _send_report_prompt(api, report, _point_of(prep) or (lat, lon))


async def _handle_address_reply(api: TelegramAPI, report: PendingReport, address: str) -> None:
    """ЛИЧКА: пользователь прислал адрес текстом (вместо гео) → AI-разбор → выбор МНО.

    ok → карта+кнопки; не распознан → принять по описанию БЕЗ привязки (чтобы не
    потерять фото/описание)."""
    prep = await prepare_max(address, photo_time=report.parsed.get("photo_time", ""))
    # Новый разбор поверх исходного, НЕ затирая непустые comment/photo_time из подписи.
    report.parsed = merge_parsed(report.parsed, prep.get("parsed") or {})

    if prep.get("status") == "ok":
        report.candidates = prep.get("candidates") or []
        report.awaiting_location = False
        report.awaiting_address = False
        _STORE.put(report)
        await api.send_message(report.chat_id, _ADDR_ACCEPTED, reply_markup=remove_reply_keyboard())
        await _send_report_prompt(api, report, _point_of(prep))
        return

    # Адрес снова не распознан → принимаем по описанию, без привязки к МНО.
    report.awaiting_location = False
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
    reply = _ADDR_UNRESOLVED + (f"\n\n{html.escape(quote)}" if quote else "")
    await api.send_message(report.chat_id, reply, reply_markup=remove_reply_keyboard())


# ---------------------------------------------------------------------------
# Группа: прямой приём фото+подписи (без интерактива).
# ---------------------------------------------------------------------------

async def _handle_group_report(
    api: TelegramAPI, *, chat_id, message_id, sender_name: str, file_id: str, text: str
) -> None:
    """ГРУППА: прямой приём (push_incident, source='telegram'), БЕЗ интерактива с МНО."""
    if not (file_id and text):
        logger.info("ignored group message chat_id=%s (нет фото или пустой текст)", chat_id)
        return
    photo = await _download_photo(api, file_id)
    if not photo:
        logger.info("ignored group message chat_id=%s (нет пригодного фото)", chat_id)
        return
    photo_time = _extract_photo_time(text)
    result = await push_incident(
        text=text,
        msg_id=str(message_id),
        sender_name=sender_name,
        photo_bytes_list=[photo],
        photo_time=photo_time,
        msg_url="",
    )
    quote = _quote_of(result)
    reply = _REPLY_ACCEPTED + (f"\n\n{html.escape(quote)}" if quote else "")
    await api.send_message(chat_id, reply)


# ---------------------------------------------------------------------------
# Диспетчер сообщений.
# ---------------------------------------------------------------------------

async def _on_message(api: TelegramAPI, message: dict) -> None:
    """Обработчик message-апдейта: маршрутизация личка/группа по chat.type."""
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = chat.get("type")
    is_group = chat_type in ("group", "supergroup")
    from_user = message.get("from") or {}
    user_id = from_user.get("id")
    sender_name = display_name(from_user)
    message_id = message.get("message_id")

    file_id = largest_photo_file_id(message)
    text = message_text(message)
    location = extract_location(message)

    try:
        # --- ГРУППА: прямой приём фото+подписи, без интерактива ---
        if is_group:
            await _handle_group_report(
                api,
                chat_id=chat_id,
                message_id=message_id,
                sender_name=sender_name,
                file_id=file_id or "",
                text=text,
            )
            return

        key = chat_key(chat_id, user_id)

        # --- ЛИЧКА ---
        # 1) Геопозиция → координаты для ожидающего обращения.
        if location is not None:
            now = time.time()
            _STORE.purge(now)
            pending = _STORE.find_awaiting(key, now=now)
            if pending is not None:
                await _handle_location(api, pending, location[0], location[1])
            else:
                # Геопозиция без ожидающего фото → просим сначала прислать фото.
                await _send_example(api, chat_id)
            return

        # 2) Новое фото → ACK + скачивание + гео-кнопка. Тяжёлое (скачивание) уводим в ФОН
        #    через _spawn — поллер не блокируется; отчёт независим (свой pending_id), гонки
        #    за общий report нет.
        if file_id:
            await api.send_chat_action(chat_id, "upload_photo")
            photo_time = _extract_photo_time(text)
            _spawn(
                _process_new_report(
                    api,
                    chat_id=chat_id,
                    user_id=user_id,
                    message_id=message_id,
                    sender_name=sender_name,
                    file_id=file_id,
                    photo_time=photo_time,
                )
            )
            return

        # 3) Текст без фото.
        if text:
            now = time.time()
            _STORE.purge(now)
            pending = _STORE.find_awaiting(key, now=now)
            if pending is not None and not _is_greeting(text):
                await _handle_address_reply(api, pending, text)
                return
            # Приветствие/команда/стороннй текст без ожидающего обращения → пример.
            await _send_example(api, chat_id)
            return

        # Ничего пригодного (стикер/голос/пустое) — молча.
        logger.info("ignored private message chat_id=%s (нет фото/локации/текста)", chat_id)

    except (AppError, IntakeError) as exc:
        logger.warning("handler error chat_id=%s: %s", chat_id, getattr(exc, "message", exc))
        await _safe_reply(api, chat_id, is_group)
    except Exception:  # noqa: BLE001 — поллер не должен умирать из-за одного сообщения
        logger.exception("unexpected error handling message chat_id=%s", chat_id)
        await _safe_reply(api, chat_id, is_group)


# ---------------------------------------------------------------------------
# Диспетчер callback (двухшаговый диалог МНО → тип → подтип).
# ---------------------------------------------------------------------------

async def _do_finalize(
    api: TelegramAPI,
    *,
    cq_id: str,
    chat_id,
    message_id,
    report: PendingReport,
    mno_id: str,
    incident_type: str,
    incident_subtype: str,
    mno_label: str,
    is_no_mno: bool,
) -> None:
    """Финал: тост + снять кнопки (удалением сообщения) → finalize → подтверждение.

    Замок report.processing ставит ВЫЗЫВАЮЩИЙ синхронно (в колбэке) — сюда входим уже
    под замком. Успех → «✅ Спасибо»; IntakeError → просьба прислать фото заново."""
    await api.answer_callback_query(cq_id, "Принято ✅")
    await api.delete_message(chat_id, message_id)
    await api.send_message(chat_id, "⏳ Идёт отправка обращения…")
    try:
        result = await _finalize(report, mno_id, incident_type, incident_subtype)
    except IntakeError:
        report.processing = False
        _STORE.put(report)
        await api.send_message(
            chat_id, "❌ Не удалось отправить. Пришлите, пожалуйста, фото площадки заново."
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
    subtype_label = _subtype_label(
        report.incident_subtypes.get(incident_type) or [], incident_subtype
    )
    if subtype_label:
        parts.append(f"Подтип: <b>{html.escape(subtype_label)}</b>")
    quote = _quote_of(result)
    if quote:
        parts.append("")
        parts.append(html.escape(quote))
    await api.send_message(chat_id, "\n".join(parts))


async def _on_callback(api: TelegramAPI, callback_query: dict) -> None:
    """Тап по кнопке. Двухшаговый диалог: шаг 1 — выбор площадки (→ спросить тип),
    шаг 2 — выбор типа (→ подтип или создать), шаг 3 — подтип (→ создать). 1:1 с maxbot.

    Против двойного создания — синхронный замок report.processing (проверка-и-установка
    без await между). Повторный тап по уже отправленному/обрабатываемому → только тост."""
    cq_id = callback_query.get("id") or ""
    data = callback_query.get("data") or ""
    msg = callback_query.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")

    try:
        mno_dec = decode_payload(data)  # (pid, idx) — шаг 1
        type_dec = decode_type_payload(data) if mno_dec is None else None
        subtype_dec = (
            decode_subtype_payload(data)
            if (mno_dec is None and type_dec is None)
            else None
        )
        if mno_dec is None and type_dec is None and subtype_dec is None:
            await api.answer_callback_query(cq_id, _CB_BAD_CHOICE)
            return
        pid = (
            mno_dec[0]
            if mno_dec is not None
            else type_dec[0]
            if type_dec is not None
            else subtype_dec[0]
        )

        _STORE.purge(time.time())
        report = _STORE.get(pid)
        if report is None:
            await api.answer_callback_query(cq_id, _CB_EXPIRED)
            return
        if report.finalized:
            await api.answer_callback_query(cq_id, _CB_ALREADY)
            return
        if report.processing:
            await api.answer_callback_query(cq_id, _CB_PROCESSING)
            return

        # Владелец диалога: тап должен прийти от того же пользователя, что начал обращение
        # (pending_id — uuid4, неугадываем; это доп. защита, не полагаемся на секретность id).
        cb_from = callback_query.get("from") or {}
        if report.user_id is not None and cb_from.get("id") != report.user_id:
            await api.answer_callback_query(cq_id, _CB_BAD_CHOICE)
            return

        # === Шаг 3: выбран подтип → создаём обращение ===
        if subtype_dec is not None:
            _, subcode = subtype_dec
            if not report.awaiting_subtype:  # устаревшая кнопка — мягко игнорируем
                await api.answer_callback_query(cq_id, _CB_PROCESSING)
                return
            mno_id = report.chosen_mno_id or ""
            report.processing = True
            _STORE.put(report)
            _spawn(
                _do_finalize(
                    api,
                    cq_id=cq_id,
                    chat_id=chat_id,
                    message_id=message_id,
                    report=report,
                    mno_id=mno_id,
                    incident_type=report.chosen_type,
                    incident_subtype=subcode,
                    mno_label=report.chosen_mno_label,
                    is_no_mno=(mno_id == ""),
                )
            )
            return

        # === Шаг 2: выбран тип → подтип (если есть) или создаём обращение ===
        if type_dec is not None:
            _, code = type_dec
            mno_id = report.chosen_mno_id or ""
            subs = report.incident_subtypes.get(code) or []
            if subs:
                if report.awaiting_subtype:  # анти-дубль повторного тапа по типу
                    await api.answer_callback_query(cq_id, _CB_PROCESSING)
                    return
                report.chosen_type = code
                report.awaiting_subtype = True
                _STORE.put(report)
                await api.answer_callback_query(cq_id, "Тип выбран")
                await api.delete_message(chat_id, message_id)
                await api.send_message(
                    chat_id, _HDR_SUBTYPE, reply_markup=_build_subtype_keyboard(pid, subs)
                )
                return
            # Тип без подтипов → создаём сразу. Замок ставим СИНХРОННО до финализации.
            report.processing = True
            _STORE.put(report)
            _spawn(
                _do_finalize(
                    api,
                    cq_id=cq_id,
                    chat_id=chat_id,
                    message_id=message_id,
                    report=report,
                    mno_id=mno_id,
                    incident_type=code,
                    incident_subtype="",
                    mno_label=report.chosen_mno_label,
                    is_no_mno=(mno_id == ""),
                )
            )
            return

        # === Шаг 1: выбрана площадка → спрашиваем тип инцидента ===
        if report.awaiting_type:  # площадка уже выбрана — повторный тап → только тост
            await api.answer_callback_query(cq_id, _CB_PROCESSING)
            return
        idx = mno_dec[1]
        if idx == NO_MNO:
            mno_id = ""
            mno_label = ""
        else:
            if not isinstance(idx, int) or idx >= len(report.candidates):
                await api.answer_callback_query(cq_id, _CB_BAD_CHOICE)
                return
            cand = report.candidates[idx]
            mno_id = str(cand.get("id") or "")
            mno_label = (cand.get("reg") or "").strip() or (cand.get("name") or "").strip()

        report.chosen_mno_id = mno_id
        report.chosen_mno_label = mno_label
        # Замок шага 1 ставим СИНХРОННО, ДО любого await (повторный тап по площадке выше
        # ловится проверкой report.awaiting_type; последовательный поллер + этот замок = без гонок).
        report.awaiting_type = True
        _STORE.put(report)
        # Площадка выбрана → карта OSM больше не нужна: удаляем её сообщение.
        if report.map_mid:
            await api.delete_message(chat_id, report.map_mid)
            report.map_mid = None

        types = report.incident_types or await fetch_incident_types()
        if types:
            report.incident_types = types
            _STORE.put(report)
            await api.answer_callback_query(cq_id, "Площадка выбрана")
            await api.delete_message(chat_id, message_id)
            await api.send_message(chat_id, _HDR_TYPE, reply_markup=_build_type_keyboard(pid, types))
            return

        # Справочник типов недоступен → создаём сразу без типа (деградация).
        report.processing = True
        _STORE.put(report)
        _spawn(
            _do_finalize(
                api,
                cq_id=cq_id,
                chat_id=chat_id,
                message_id=message_id,
                report=report,
                mno_id=mno_id,
                incident_type="",
                incident_subtype="",
                mno_label=mno_label,
                is_no_mno=(idx == NO_MNO),
            )
        )

    except Exception:  # noqa: BLE001 — поллер не должен умирать из-за одного колбэка
        logger.exception("unexpected error handling callback")
        try:
            await api.answer_callback_query(cq_id, _CB_FINALIZE_FAIL)
        except Exception:  # noqa: BLE001
            logger.exception("failed to send callback error notification")


async def dispatch(api: TelegramAPI, update: dict) -> None:
    """Маршрутизация одного апдейта. Внешний try/except — поллер не умирает никогда."""
    try:
        kind = update_kind(update)
        if kind == "callback_query":
            await _on_callback(api, update["callback_query"])
        elif kind == "message":
            await _on_message(api, update["message"])
        else:
            logger.debug("skip unsupported update: keys=%s", list(update.keys()) if isinstance(update, dict) else type(update))
    except Exception:  # noqa: BLE001
        logger.exception("dispatch failed for update_id=%s", update.get("update_id") if isinstance(update, dict) else "?")


async def _safe_reply(api: TelegramAPI, chat_id, is_group: bool) -> None:
    """Best-effort мягкая ошибка; в группе молчим (бот не болтает)."""
    if is_group or chat_id is None:
        return
    try:
        await api.send_message(chat_id, _REPLY_SOFT_ERROR)
    except Exception:  # noqa: BLE001
        logger.exception("failed to send soft-error reply")
