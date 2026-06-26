"""HTTP-клиент к backend intake API.

Сервисный слой: принимает текст/идентификаторы/байты фото, делает multipart
POST на INTAKE_URL с общим секретом X-Intake-Token. На сетевые сбои и не-2xx
ответы поднимает AppError (IntakeError) — НЕ HTTPException: это воркер, а не
FastAPI-приложение. Вызывающий код (обработчик сообщения) сам решает, что
ответить пользователю.
"""

from __future__ import annotations

import logging

import httpx

from .config import settings
from .errors import IntakeError

logger = logging.getLogger("dedecology.maxbot")

# Backend может перекодировать фото; даём запас на запись инцидента.
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


async def push_incident(
    text: str,
    msg_id: str,
    sender_name: str,
    photo_bytes_list: list[bytes],
) -> dict:
    """Передаёт обращение из MAX в backend intake API и возвращает разобранный JSON.

    :param text: Текст сообщения (может быть пустым, если прислали только фото).
    :param msg_id: Идентификатор исходного сообщения MAX (mid) — для дедупликации/трейса.
    :param sender_name: Отображаемое имя отправителя (или его user_id строкой).
    :param photo_bytes_list: Байты фото (как правило, одно — первое изображение).
    :raises IntakeError: при сетевой ошибке, таймауте или не-2xx ответе backend.
    """
    data = {
        "text": text,
        "msg_id": msg_id,
        "sender_name": sender_name,
    }
    files = [
        ("photos", (f"{i}.jpg", photo, "image/jpeg"))
        for i, photo in enumerate(photo_bytes_list)
    ]
    headers = {"X-Intake-Token": settings.INTAKE_TOKEN}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                settings.INTAKE_URL,
                data=data,
                files=files or None,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        logger.error(
            "intake request failed (network) msg_id=%s url=%s: %s",
            msg_id,
            settings.INTAKE_URL,
            exc,
        )
        raise IntakeError(f"Не удалось связаться с intake API: {exc}") from exc

    if not resp.is_success:
        body_preview = resp.text[:500]
        logger.error(
            "intake API returned %s for msg_id=%s: %s",
            resp.status_code,
            msg_id,
            body_preview,
        )
        raise IntakeError(
            f"Intake API ответил {resp.status_code}",
            status_code=502,
            details={"backend_status": resp.status_code, "body": body_preview},
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        logger.error("intake API returned non-JSON for msg_id=%s: %s", msg_id, resp.text[:500])
        raise IntakeError("Intake API вернул не-JSON ответ") from exc

    logger.info(
        "intake accepted msg_id=%s photos=%d response=%s",
        msg_id,
        len(photo_bytes_list),
        payload,
    )
    return payload
