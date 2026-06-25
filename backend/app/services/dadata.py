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
DADATA_TIMEOUT = 8


async def suggest_address(query: str, count: int = 8) -> list[dict]:
    """Подсказки адресов по строке ввода.

    Возвращает список словарей с полями:
    value, region, city, street, coords, geo_lat, geo_lon.

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
    payload = {"query": q, "count": count}

    try:
        async with httpx.AsyncClient(timeout=DADATA_TIMEOUT) as http_client:
            resp = await http_client.post(
                DADATA_SUGGEST_URL, json=payload, headers=headers
            )
        resp.raise_for_status()
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
            }
        )
    return out
