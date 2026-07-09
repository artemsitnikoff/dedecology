"""HTTP-клиент к backend intake API.

Сервисный слой: принимает текст/идентификаторы/байты фото, делает multipart
POST на INTAKE_URL с общим секретом X-Intake-Token. На сетевые сбои и не-2xx
ответы поднимает AppError (IntakeError) — НЕ HTTPException: это воркер, а не
FastAPI-приложение. Вызывающий код (обработчик сообщения) сам решает, что
ответить пользователю.
"""

from __future__ import annotations

import logging
import time

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

# Карта — НЕ критична (деградируем до текста): короткий таймаут, чтобы медленный
# рендер OSM не задерживал показ списка площадок с кнопками.
_MAP_TIMEOUT = httpx.Timeout(7.0, connect=4.0)


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


async def prepare_max(text: str, photo_time: str = "") -> dict:
    """Разбор адреса + поиск ближайших МНО БЕЗ создания обращения.

    POST {api_base}/intake/max/prepare (JSON, X-Intake-Token). Возвращает dict
    контракта: `{"status":"need_address"|"ok", "parsed":{...}, "point":{...},
    "candidates":[...]}`.

    :param text: Текст-описание (подпись к фото или присланный адрес).
    :param photo_time: ISO "%Y-%m-%dT%H:%M" — время фотофиксации из подписи
        (fallback для backend, если AI не извлёк время). Пустая строка → не шлём.
    :raises IntakeError: сеть/таймаут/не-2xx/не-JSON — вызывающий отвечает мягко.
    """
    url = f"{settings.api_base}/intake/max/prepare"
    headers = {"X-Intake-Token": settings.INTAKE_TOKEN}
    body: dict = {"text": text}
    if photo_time:
        body["photo_time"] = photo_time

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=body, headers=headers)
    except httpx.HTTPError as exc:
        logger.error("prepare_max request failed url=%s: %s", url, exc)
        raise IntakeError(f"Не удалось связаться с intake API: {exc}") from exc

    if not resp.is_success:
        body_preview = resp.text[:500]
        logger.error("prepare_max returned %s: %s", resp.status_code, body_preview)
        raise IntakeError(
            f"prepare ответил {resp.status_code}",
            details={"backend_status": resp.status_code, "body": body_preview},
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        logger.error("prepare_max non-JSON: %s", resp.text[:500])
        raise IntakeError("prepare вернул не-JSON ответ") from exc

    logger.info(
        "prepare_max status=%s candidates=%d",
        payload.get("status") if isinstance(payload, dict) else "?",
        len(payload.get("candidates") or []) if isinstance(payload, dict) else 0,
    )
    return payload


async def finalize_max(
    *,
    region: str,
    city: str,
    street: str,
    coords: str,
    comment: str,
    photo_time: str,
    msg_id: str,
    sender_name: str,
    msg_url: str,
    mno_id: str,
    photo_bytes_list: list[bytes],
    incident_type: str = "",
) -> dict:
    """Создать обращение (source='max') из уже разобранных полей + выбранного МНО.

    POST {api_base}/intake/max/finalize (multipart, X-Intake-Token). AI на
    backend НЕ дёргается повторно. `mno_id=""` → «Нет в списке» (без привязки).
    `incident_type` — код из справочника (пусто/неизвестный → NULL на бэке).

    :raises IntakeError: сеть/таймаут/не-2xx/не-JSON.
    """
    url = f"{settings.api_base}/intake/max/finalize"
    headers = {"X-Intake-Token": settings.INTAKE_TOKEN}
    # None-безопасность: Form-поля должны быть строками, не «None».
    data = {
        "region": region or "",
        "city": city or "",
        "street": street or "",
        "coords": coords or "",
        "comment": comment or "",
        "photo_time": photo_time or "",
        "msg_id": msg_id or "",
        "sender_name": sender_name or "",
        "msg_url": msg_url or "",
        "mno_id": mno_id or "",
        "incident_type": incident_type or "",
    }
    files = [
        ("photos", (f"{i}.jpg", photo, "image/jpeg"))
        for i, photo in enumerate(photo_bytes_list)
    ]

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, data=data, files=files or None, headers=headers)
    except httpx.HTTPError as exc:
        logger.error("finalize_max request failed url=%s: %s", url, exc)
        raise IntakeError(f"Не удалось связаться с intake API: {exc}") from exc

    if not resp.is_success:
        body_preview = resp.text[:500]
        logger.error("finalize_max returned %s: %s", resp.status_code, body_preview)
        raise IntakeError(
            f"finalize ответил {resp.status_code}",
            details={"backend_status": resp.status_code, "body": body_preview},
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        logger.error("finalize_max non-JSON: %s", resp.text[:500])
        raise IntakeError("finalize вернул не-JSON ответ") from exc

    logger.info(
        "finalize_max ok incident=%s mno_id=%s photos=%d",
        payload.get("incident_id") if isinstance(payload, dict) else "?",
        mno_id or "-",
        len(photo_bytes_list),
    )
    return payload


async def fetch_map(lat: float, lon: float, pts: str) -> bytes | None:
    """Скачать PNG-скрин карты (точка обращения + метки МНО) у backend.

    GET {api_base}/intake/max/map?lat&lon&pts (X-Intake-Token). Возвращает
    байты PNG или None при ЛЮБОЙ ошибке / не-2xx / пустом ответе — бот тогда
    деградирует до текстового списка без картинки (карта не критична).
    """
    url = f"{settings.api_base}/intake/max/map"
    headers = {"X-Intake-Token": settings.INTAKE_TOKEN}
    params = {"lat": lat, "lon": lon, "pts": pts}
    try:
        async with httpx.AsyncClient(timeout=_MAP_TIMEOUT) as client:
            resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("fetch_map failed url=%s: %s", url, exc)
        return None
    content = resp.content
    if not content:
        logger.warning("fetch_map returned empty body url=%s", url)
        return None
    return content


# Кэш справочника типов: он редко меняется, а на тапе по площадке нужен мгновенно.
# TTL 5 минут; при ошибке НЕ кэшируем (следующий вызов попробует снова).
_TYPES_CACHE: dict = {"at": 0.0, "data": []}
_TYPES_TTL = 300.0


async def fetch_incident_types() -> list[dict]:
    """Справочник типов инцидента [{code,label}] для кнопок выбора (шаг 2 диалога).

    GET {api_base}/intake/incident-types (публичный эндпоинт — тот же, что у формы).
    Кэшируется на _TYPES_TTL сек (справочник статичный) — чтобы шаг выбора типа
    открывался без сетевого запроса. При ЛЮБОЙ ошибке / не-2xx / неожиданном формате
    → [] (бот пропускает выбор типа и создаёт обращение без типа — деградация, не фейл).
    """
    now = time.monotonic()
    if _TYPES_CACHE["data"] and (now - _TYPES_CACHE["at"] < _TYPES_TTL):
        return _TYPES_CACHE["data"]

    url = f"{settings.api_base}/intake/incident-types"
    try:
        async with httpx.AsyncClient(timeout=_NOTIFY_TIMEOUT) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("fetch_incident_types failed url=%s: %s", url, exc)
        return []
    if not isinstance(payload, list):
        logger.warning("fetch_incident_types: unexpected payload: %r", payload)
        return []
    # Оставляем только валидные {code,label}.
    out = [
        {"code": str(t.get("code") or ""), "label": str(t.get("label") or "")}
        for t in payload
        if isinstance(t, dict) and t.get("code")
    ]
    if out:
        _TYPES_CACHE["data"] = out
        _TYPES_CACHE["at"] = now
    return out


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
