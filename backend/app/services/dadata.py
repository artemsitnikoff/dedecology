"""DaData — онлайн-подсказки адресов для автозаполнения публичной формы.

Использует suggest/address (полный адрес — регион/город/улица/дом), чтобы
волонтёр выбирал реальный адрес из выпадающего списка.

Если ключ не задан, запрос короче 3 символов или DaData недоступна —
возвращаем graceful [] (никогда не роняем форму 500-кой).
"""

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

DADATA_SUGGEST_URL = (
    "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
)
DADATA_CLEAN_ADDRESS_URL = "https://cleaner.dadata.ru/api/v1/clean/address"
DADATA_TIMEOUT = 8


async def suggest_address(
    query: str,
    count: int = 8,
    from_bound: str | None = None,
    to_bound: str | None = None,
    locations: list[dict] | None = None,
) -> list[dict]:
    """Подсказки адресов по строке ввода.

    Возвращает список словарей с полями:
    value, region, city, street, coords, geo_lat, geo_lon.

    Поддержка ограниченных (bounded) подсказок:
    - from_bound/to_bound сужают уровень адреса (region / city / settlement /
      street / house) — передаются в DaData как {"value": <bound>};
    - locations — список фильтров вида [{"region": "..."}] или
      [{"region": "...", "city": "..."}] — ограничивает географию подсказок.

    [] если ключ не задан, query короче 3 символов или DaData недоступна.
    """
    q = (query or "").strip()
    if not settings.DADATA_API_KEY or len(q) < 3:
        return []
    # Отсекаем чрезмерно длинный ввод до отправки во внешний сервис.
    q = q[:200]

    headers = {
        "Authorization": f"Token {settings.DADATA_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload: dict = {"query": q, "count": count}
    if from_bound:
        payload["from_bound"] = {"value": from_bound}
    if to_bound:
        payload["to_bound"] = {"value": to_bound}
    if locations:
        payload["locations"] = locations

    try:
        async with httpx.AsyncClient(timeout=DADATA_TIMEOUT) as http_client:
            resp = await http_client.post(
                DADATA_SUGGEST_URL, json=payload, headers=headers
            )
        # Статус (без тела — без секретов) логируем при не-200 и деградируем в [].
        if resp.status_code != 200:
            logger.warning("[dadata] suggest non-200: %s", resp.status_code)
            return []
        data = resp.json()
    except Exception as e:  # graceful: любой сбой → без подсказок, форма жива
        logger.warning("[dadata] suggest_address failed: %s: %s", type(e).__name__, e)
        return []

    out: list[dict] = []
    for s in data.get("suggestions", []):
        d = s.get("data") or {}
        geo_lat = d.get("geo_lat") or ""
        geo_lon = d.get("geo_lon") or ""
        coords = f"{geo_lat}, {geo_lon}" if geo_lat and geo_lon else ""
        out.append(
            {
                "value": s.get("value") or "",
                "region": d.get("region_with_type") or d.get("region") or "",
                "city": (
                    d.get("city_with_type")
                    or d.get("settlement_with_type")
                    or d.get("city")
                    or ""
                ),
                "street": d.get("street_with_type") or "",
                "coords": coords,
                "geo_lat": geo_lat,
                "geo_lon": geo_lon,
                # Голые имена (без типа) — DaData фильтрует locations именно по ним
                # ("Самарская", "Кинель"), а не по "Самарская обл" / "г Кинель".
                "region_plain": d.get("region") or "",
                "city_plain": d.get("city") or d.get("settlement") or "",
            }
        )
    return out


async def clean_address(raw: str) -> dict | None:
    """Разбор свободного текста адреса через DaData Clean API.

    Применяется для входящих Макс-сообщений: пользователь присылает адрес
    одной строкой, мы стандартизируем его в регион/город/улицу + координаты.

    Clean API требует ОБА ключа (Authorization: Token + X-Secret). Если хотя бы
    один не задан, raw пустой, DaData недоступна или ответ не-200 — возвращаем
    None (вызывающий код деградирует на эвристический разбор).

    Returns: {region, city, street, coords, geo_lat, geo_lon} или None.
    """
    text_value = (raw or "").strip()
    if not text_value:
        return None
    if not settings.DADATA_API_KEY or not settings.DADATA_SECRET_KEY:
        logger.debug("[dadata] clean_address: ключи Clean API не настроены")
        return None

    # Отсекаем чрезмерно длинный ввод до отправки во внешний сервис.
    text_value = text_value[:300]

    headers = {
        "Authorization": f"Token {settings.DADATA_API_KEY}",
        "X-Secret": settings.DADATA_SECRET_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=DADATA_TIMEOUT) as http_client:
            resp = await http_client.post(
                DADATA_CLEAN_ADDRESS_URL, json=[text_value], headers=headers
            )
        if resp.status_code != 200:
            logger.warning("[dadata] clean_address non-200: %s", resp.status_code)
            return None
        data = resp.json()
    except Exception as e:  # graceful: любой сбой → None, разбор уходит в эвристику
        logger.warning(
            "[dadata] clean_address failed: %s: %s", type(e).__name__, e
        )
        return None

    if not isinstance(data, list) or not data:
        return None
    d = data[0] or {}

    geo_lat = d.get("geo_lat") or ""
    geo_lon = d.get("geo_lon") or ""
    coords = f"{geo_lat}, {geo_lon}" if geo_lat and geo_lon else ""
    return {
        "region": d.get("region_with_type") or d.get("region") or "",
        "city": (
            d.get("city_with_type")
            or d.get("settlement_with_type")
            or d.get("city")
            or ""
        ),
        "street": d.get("street_with_type") or "",
        "coords": coords,
        "geo_lat": geo_lat,
        "geo_lon": geo_lon,
    }
