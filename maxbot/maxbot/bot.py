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

import logging
import re
from datetime import datetime
from pathlib import Path

import httpx
from maxapi import Bot, Router
from maxapi.client.default import DefaultConnectionProperties
from maxapi.enums.attachment import AttachmentType
from maxapi.types import CommandStart, InputMediaBuffer, MessageCreated
from maxapi.types.attachments.image import Image
from maxapi.types.message import Message

from .config import settings
from .errors import AppError
from .intake_client import push_incident

logger = logging.getLogger("dedecology.maxbot")

_DOWNLOAD_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Точный пример подписи БЕЗ опционального района — используется как образец в UI.
EXAMPLE = (
    "Московская область, г. Голицыно, ул. Советская д.56/2 "
    "напротив подъезда 2. Время 19:30"
)

# Время на фото: «Время 19:30», «время 9.05» и т.п. Группы: часы и минуты.
_TIME_RE = re.compile(r"врем[яи][\s:]*([0-2]?\d)[:.]([0-5]\d)", re.IGNORECASE)

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
        try:
            body = msg.body
            text = ((body.text if body else None) or "").strip()
            mid = body.mid if body else ""
            sender_name = _sender_display_name(msg.sender)
            images = _all_images(msg)

            # Приветствие/пустое сообщение без фото → показываем пример.
            if not images and _is_greeting(text):
                await _send_example(msg)
                return

            # Строгая отправка: нужно ФОТО + время «Время ЧЧ:ММ» + непустой адрес.
            if images:
                match = _TIME_RE.search(text)
                if match:
                    address = text[: match.start()].strip(" \t\r\n.,;")
                    hour = int(match.group(1))
                    minute = int(match.group(2))
                    if address and hour <= 23:
                        # Скачиваем ВСЕ картинки (до 3); сбойную/слишком большую — пропускаем.
                        photos: list[bytes] = []
                        for img in images:
                            try:
                                photos.append(
                                    await _download_image(img, max_bytes=settings.MAX_PHOTO_BYTES)
                                )
                            except AppError as exc:
                                logger.warning("skip image mid=%s: %s", mid, exc.code)
                        if photos:
                            photo_time = (
                                datetime.now()
                                .replace(hour=hour, minute=minute, second=0, microsecond=0)
                                .strftime("%Y-%m-%dT%H:%M")
                            )
                            result = await push_incident(
                                text=address,
                                msg_id=str(mid),
                                sender_name=sender_name,
                                photo_bytes_list=photos,
                                photo_time=photo_time,
                            )
                            # Бэк возвращает мотивирующую цитату о природе — дописываем к ответу.
                            quote = ""
                            if isinstance(result, dict):
                                quote = (result.get("quote") or "").strip()
                            reply = _REPLY_ACCEPTED + (f"\n\n{quote}" if quote else "")
                            await msg.answer(text=reply)
                            return

            # Всё остальное (нет фото / нет времени / пустой адрес) — подсказка по формату.
            await msg.answer(text=_REPLY_INVALID_FORMAT)

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

    return router


async def _safe_reply(msg: Message) -> None:
    """Best-effort soft error reply; swallow secondary failures."""
    try:
        await msg.answer(text=_REPLY_SOFT_ERROR)
    except Exception:  # noqa: BLE001
        logger.exception("failed to send soft-error reply")
