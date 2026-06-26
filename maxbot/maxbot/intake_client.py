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

# Опрос/пометка уведомлений — лёгкие JSON-запросы, короткий таймаут.
_NOTIFY_TIMEOUT = httpx.Timeout(15.0, connect=10.0)

# Скачивание фото для пересылки в групповой чат — потоково, с потолком размера.
_PHOTO_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def push_incident(
    text: str,
    msg_id: str,
    sender_name: str,
    photo_bytes_list: list[bytes],
    photo_time: str | None = None,
    msg_url: str = "",
) -> dict:
    """Передаёт обращение из MAX в backend intake API и возвращает разобранный JSON.

    :param text: Текст сообщения (адрес площадки; может быть пустым, если прислали только фото).
    :param msg_id: Идентификатор исходного сообщения MAX (mid) — для дедупликации/трейса.
    :param sender_name: Отображаемое имя отправителя (или его user_id строкой).
    :param photo_bytes_list: Байты фото (как правило, одно — первое изображение).
    :param photo_time: Время на фото в ISO-формате "%Y-%m-%dT%H:%M" (опционально).
        Если задано — отправляется multipart-полем `photo_time`; иначе поле не добавляется,
        и контракт остаётся прежним.
    :param msg_url: Готовый полный https-URL сообщения MAX (Message.url). Для лички с ботом
        обычно пустой — тогда ссылку нигде не показываем. Всегда отправляется multipart-полем
        `msg_url` (пустая строка по умолчанию).
    :raises IntakeError: при сетевой ошибке, таймауте или не-2xx ответе backend.
    """
    data = {
        "text": text,
        "msg_id": msg_id,
        "sender_name": sender_name,
        "msg_url": msg_url,
    }
    if photo_time is not None:
        data["photo_time"] = photo_time
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
        "intake accepted msg_id=%s photos=%d photo_time=%s response=%s",
        msg_id,
        len(photo_bytes_list),
        photo_time,
        payload,
    )
    return payload


async def fetch_pending() -> list[dict]:
    """Забрать у backend обращения, ещё не отправленные в групповой чат.

    GET {api_base}/intake/pending-notify с X-Intake-Token.
    На любую ошибку (сеть, не-2xx, кривой JSON) возвращает [] — фоновый цикл
    должен пережить недоступность backend и повторить на следующей итерации.
    """
    url = f"{settings.api_base}/intake/pending-notify"
    headers = {"X-Intake-Token": settings.INTAKE_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=_NOTIFY_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("fetch_pending failed url=%s: %s", url, exc)
        return []

    incidents = payload.get("incidents") if isinstance(payload, dict) else None
    if not isinstance(incidents, list):
        logger.error("fetch_pending: unexpected payload shape: %r", payload)
        return []
    return incidents


async def mark_notified(ids: list[str]) -> None:
    """Пометить обращения отправленными: POST {api_base}/intake/mark-notified.

    :param ids: Список UUID-строк обращений, успешно запостенных в чат.
    :raises IntakeError: при сетевой ошибке/таймауте или не-2xx ответе backend
        — вызывающий цикл логирует и продолжает (обращения переотправятся).
    """
    if not ids:
        return
    url = f"{settings.api_base}/intake/mark-notified"
    headers = {"X-Intake-Token": settings.INTAKE_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=_NOTIFY_TIMEOUT) as client:
            resp = await client.post(url, json={"ids": ids}, headers=headers)
    except httpx.HTTPError as exc:
        logger.error("mark_notified request failed url=%s: %s", url, exc)
        raise IntakeError(f"Не удалось пометить обращения отправленными: {exc}") from exc

    if not resp.is_success:
        body_preview = resp.text[:500]
        logger.error("mark_notified returned %s: %s", resp.status_code, body_preview)
        raise IntakeError(
            f"mark-notified ответил {resp.status_code}",
            details={"backend_status": resp.status_code, "body": body_preview},
        )

    logger.info("mark_notified ok count=%d", len(ids))


async def download_photo(url_path: str) -> bytes | None:
    """Скачать фото инцидента по относительному пути (backend_origin + url_path).

    Эндпоинт фото публичный (без X-Intake-Token). Потоково с потолком
    settings.MAX_PHOTO_BYTES. На любую ошибку/превышение размера → None.
    """
    if not url_path:
        return None
    # Поддерживаем как относительные (/api/v1/...), так и абсолютные URL.
    url = url_path if url_path.startswith(("http://", "https://")) else (
        settings.backend_origin + url_path
    )
    try:
        async with httpx.AsyncClient(
            timeout=_PHOTO_TIMEOUT, follow_redirects=True
        ) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > settings.MAX_PHOTO_BYTES:
                        logger.warning(
                            "download_photo too large (> %d bytes) url=%s",
                            settings.MAX_PHOTO_BYTES,
                            url,
                        )
                        return None
                    chunks.append(chunk)
    except httpx.HTTPError as exc:
        logger.error("download_photo failed url=%s: %s", url, exc)
        return None
    return b"".join(chunks)
