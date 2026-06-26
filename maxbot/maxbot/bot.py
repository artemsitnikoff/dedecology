"""MAX bot wiring: bot factory, attachment helpers and the message handler.

The handler is the only business entrypoint: it extracts the message text and
the first photo, downloads the photo bytes, forwards everything to the backend
intake API and replies to the user. Every failure is caught, logged and turned
into a soft reply so the long-polling loop never dies.
"""

from __future__ import annotations

import logging

import httpx
from maxapi import Bot, Router
from maxapi.client.default import DefaultConnectionProperties
from maxapi.enums.attachment import AttachmentType
from maxapi.types import MessageCreated
from maxapi.types.attachments.image import Image
from maxapi.types.message import Message

from .config import settings
from .errors import AppError
from .intake_client import push_incident

logger = logging.getLogger("dedecology.maxbot")

_DOWNLOAD_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_REPLY_ACCEPTED = "Спасибо! Обращение принято и передано инспектору."
_REPLY_NEED_PHOTO = (
    "Пожалуйста, пришлите фотографию места и текстом укажите адрес — "
    "так инспектор сможет выехать и разобраться."
)
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


def _first_image(msg: Message) -> Image | None:
    """Return the first IMAGE attachment of the message, or None."""
    if not msg.body or not msg.body.attachments:
        return None
    for att in msg.body.attachments:
        if isinstance(att, Image) or getattr(att, "type", None) == AttachmentType.IMAGE:
            return att  # type: ignore[return-value]
    return None


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


def build_router() -> Router:
    """Build the router with the single message_created handler."""
    router = Router()

    @router.message_created()
    async def on_message_created(event: MessageCreated) -> None:
        msg = event.message
        try:
            body = msg.body
            text = (body.text if body else None) or ""
            text = text.strip()
            mid = body.mid if body else ""

            sender = msg.sender
            sender_name = ""
            if sender is not None:
                first = (sender.first_name or "").strip()
                last = (sender.last_name or "").strip()
                sender_name = f"{first} {last}".strip() or str(sender.user_id)

            image = _first_image(msg)

            # Ни текста, ни фото — подсказываем, что прислать.
            if not text and image is None:
                await msg.answer(text=_REPLY_NEED_PHOTO)
                return

            photo_bytes_list: list[bytes] = []
            if image is not None:
                photo = await _download_image(image, max_bytes=settings.MAX_PHOTO_BYTES)
                photo_bytes_list.append(photo)

            await push_incident(
                text=text,
                msg_id=str(mid),
                sender_name=sender_name,
                photo_bytes_list=photo_bytes_list,
            )
            await msg.answer(text=_REPLY_ACCEPTED)

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
