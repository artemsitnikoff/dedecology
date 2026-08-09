"""HTTP-клиент к backend intake API.

Сервисный слой: принимает текст/идентификаторы/байты фото, делает multipart/JSON
POST на backend intake с общим секретом X-Intake-Token. На сетевые сбои и не-2xx
ответы поднимает AppError (IntakeError) — НЕ HTTPException: это воркер, а не
FastAPI-приложение. Вызывающий код (обработчик сообщения) сам решает, что
ответить пользователю.

Перенесён из maxbot/intake_client.py. Отличия Telegram-трека:
  * push_incident / finalize_max шлют дополнительное поле source="telegram"
    (backend whitelist {'max','telegram'}); обращение видно в админке как «Telegram».
  * добавлена prepare_coords(lat, lon) → POST /intake/max/prepare-coords (гео-кнопка).
"""

from __future__ import annotations

import logging
import time

import httpx

from .config import settings
from .errors import IntakeError

logger = logging.getLogger("dedecology.telegrambot")

# Канал приёма для backend (поле multipart-формы source). Backend нормализует к
# whitelist {'max','telegram'} — обращения из Telegram помечаются отдельно.
SOURCE = "telegram"

# Backend может перекодировать фото; даём запас на запись инцидента.
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# Лёгкие JSON-запросы (справочники) — короткий таймаут.
_NOTIFY_TIMEOUT = httpx.Timeout(15.0, connect=10.0)

# Скачивание фото для пересылки — потоково, с потолком размера.
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
    """Передаёт обращение из Telegram в backend intake API (source='telegram').

    Прямой приём (групповой сценарий): фото+подпись → обращение сразу, без
    интерактива с МНО.

    :param text: Текст сообщения (адрес площадки; может быть пустым).
    :param msg_id: Идентификатор исходного сообщения Telegram (message_id) — для трейса.
    :param sender_name: Отображаемое имя отправителя (или его user_id строкой).
    :param photo_bytes_list: Байты фото.
    :param photo_time: Время на фото в ISO "%Y-%m-%dT%H:%M" (опционально).
    :param msg_url: Готовый URL сообщения (для Telegram-лички/группы обычно пустой).
    :raises IntakeError: при сетевой ошибке, таймауте или не-2xx ответе backend.
    """
    data = {
        "text": text,
        "msg_id": msg_id,
        "sender_name": sender_name,
        "msg_url": msg_url,
        "source": SOURCE,
    }
    if photo_time is not None:
        data["photo_time"] = photo_time
    files = [
        ("photos", (f"{i}.jpg", photo, "image/jpeg"))
        for i, photo in enumerate(photo_bytes_list)
    ]
    headers = {"X-Intake-Token": settings.INTAKE_TOKEN.get_secret_value()}

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
    """Разбор адреса (AI) + поиск ближайших МНО БЕЗ создания обращения — ТЕКСТОВЫЙ фолбэк.

    POST {api_base}/intake/max/prepare (JSON, X-Intake-Token). Возвращает dict
    контракта: `{"status":"need_address"|"ok", "parsed":{...}, "point":{...},
    "candidates":[...]}`.

    :param text: Присланный пользователем адрес (когда вместо гео-кнопки прислал текст).
    :param photo_time: ISO "%Y-%m-%dT%H:%M" — время фотофиксации из подписи (fallback).
    :raises IntakeError: сеть/таймаут/не-2xx/не-JSON — вызывающий отвечает мягко.
    """
    url = f"{settings.api_base}/intake/max/prepare"
    headers = {"X-Intake-Token": settings.INTAKE_TOKEN.get_secret_value()}
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


async def prepare_coords(lat: float, lon: float, photo_time: str = "") -> dict:
    """Coords-first разбор: ближайшие МНО по ТОЧНЫМ координатам (гео-кнопка Telegram).

    POST {api_base}/intake/max/prepare-coords (JSON, X-Intake-Token). AI/resolve_address
    НЕ дёргаются — сразу nearest_mno. Возвращает dict по ТОМУ ЖЕ контракту, что
    prepare_max (ветка "ok"): `{"status":"ok","parsed":{coords,region="",city="",
    street="",comment="",photo_time},"point":{lat,lon},"candidates":[...]}`. Рядом
    пусто → candidates=[], status всё равно "ok".

    :param lat: Широта присланной геопозиции.
    :param lon: Долгота присланной геопозиции.
    :param photo_time: ISO "%Y-%m-%dT%H:%M" — время фотофиксации из подписи (опц.).
    :raises IntakeError: сеть/таймаут/не-2xx/не-JSON — вызывающий отвечает мягко.
    """
    url = f"{settings.api_base}/intake/max/prepare-coords"
    headers = {"X-Intake-Token": settings.INTAKE_TOKEN.get_secret_value()}
    body: dict = {"lat": lat, "lon": lon}
    if photo_time:
        body["photo_time"] = photo_time

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=body, headers=headers)
    except httpx.HTTPError as exc:
        logger.error("prepare_coords request failed url=%s: %s", url, exc)
        raise IntakeError(f"Не удалось связаться с intake API: {exc}") from exc

    if not resp.is_success:
        body_preview = resp.text[:500]
        logger.error("prepare_coords returned %s: %s", resp.status_code, body_preview)
        raise IntakeError(
            f"prepare-coords ответил {resp.status_code}",
            details={"backend_status": resp.status_code, "body": body_preview},
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        logger.error("prepare_coords non-JSON: %s", resp.text[:500])
        raise IntakeError("prepare-coords вернул не-JSON ответ") from exc

    logger.info(
        "prepare_coords status=%s candidates=%d",
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
    incident_subtype: str = "",
) -> dict:
    """Создать обращение (source='telegram') из уже разобранных полей + выбранного МНО.

    POST {api_base}/intake/max/finalize (multipart, X-Intake-Token). AI на
    backend НЕ дёргается повторно. `mno_id=""` → «Нет в списке» (без привязки).
    `incident_type` — код из справочника (пусто/неизвестный → NULL на бэке).

    :raises IntakeError: сеть/таймаут/не-2xx/не-JSON.
    """
    url = f"{settings.api_base}/intake/max/finalize"
    headers = {"X-Intake-Token": settings.INTAKE_TOKEN.get_secret_value()}
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
        "incident_subtype": incident_subtype or "",
        "source": SOURCE,
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
    headers = {"X-Intake-Token": settings.INTAKE_TOKEN.get_secret_value()}
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
    Кэшируется на _TYPES_TTL сек (справочник статичный). При ЛЮБОЙ ошибке / не-2xx /
    неожиданном формате → [] (бот пропускает выбор типа — деградация, не фейл).
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


# Кэш карты подтипов (редко меняется). {type_code: [{code,label}]}.
_SUBTYPES_CACHE: dict = {"at": 0.0, "data": {}}
_SUBTYPES_TTL = 300.0


async def fetch_incident_subtypes() -> dict:
    """Карта подтипов {type_code: [{code,label}]} для шага 3 (тип с подтипами).

    GET {api_base}/intake/incident-subtypes (публичный эндпоинт, тот же, что у формы).
    Кэш TTL 5 мин. При ЛЮБОЙ ошибке / не-2xx / неожиданном формате → {} (бот пропускает
    шаг подтипа — деградация, не фейл)."""
    now = time.monotonic()
    if _SUBTYPES_CACHE["data"] and (now - _SUBTYPES_CACHE["at"] < _SUBTYPES_TTL):
        return _SUBTYPES_CACHE["data"]

    url = f"{settings.api_base}/intake/incident-subtypes"
    try:
        async with httpx.AsyncClient(timeout=_NOTIFY_TIMEOUT) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("fetch_incident_subtypes failed url=%s: %s", url, exc)
        return {}
    if not isinstance(payload, dict):
        logger.warning("fetch_incident_subtypes: unexpected payload: %r", payload)
        return {}
    # Оставляем только валидные {type_code: [{code,label}]}.
    out: dict = {}
    for type_code, subs in payload.items():
        if not isinstance(subs, list):
            continue
        out[str(type_code)] = [
            {"code": str(s.get("code") or ""), "label": str(s.get("label") or "")}
            for s in subs
            if isinstance(s, dict) and s.get("code")
        ]
    if out:
        _SUBTYPES_CACHE["data"] = out
        _SUBTYPES_CACHE["at"] = now
    return out


async def download_photo(url_path: str) -> bytes | None:
    """Скачать фото обращения по относительному пути (backend_origin + url_path).

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
