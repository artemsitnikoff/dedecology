"""Async-клиент публичного API ФГИС УТКО (карта «Места накопления», слой 5).

Живой публичный API Минприроды. Все запросы — httpx.AsyncClient. Тайл-эндпоинт
отдаёт JSONP (`callback({...});`), поэтому ответ снимаем регуляркой и json.loads.

Ошибки транспорта/ФГИС → AppError (никогда HTTPException) — единый конверт ошибок.
Тайл-запрос устойчив к HTTP 500 (слишком большой bbox для зума) — деградирует в []
без падения обхода.

Краулер `enumerate_region_mno_ids` перечисляет ВСЕ id МНО региона обходом ячеек карты
(BFS): большие кластеры дробятся 2×2 с ростом зума, пока не станут «читаемыми» (<=100
объектов, массив ids полный) либо не упрёмся в MAX_Z.
"""

import json
import logging
import re
import uuid
from collections.abc import Callable

import httpx

from ..config import settings
from ..core.errors import AppError

logger = logging.getLogger(__name__)

# --- Константы API -------------------------------------------------------------

MAP_API_PREFIX = "/reo-fs-public-map-api/api/v2.0"
LAYER = 5  # слой «места накопления отходов»
FGIS_TIMEOUT = 40

# --- Константы обхода (краулер) ------------------------------------------------

# Стартовые ячейки покрывают РФ колонками ~43° по долготе при START_Z=4.
# Региональный фильтр => в нерелевантных ячейках фич просто нет.
START_CELLS: list[tuple[float, float, float, float]] = [
    (19, 41, 62, 82),
    (62, 41, 105, 82),
    (105, 41, 148, 82),
    (148, 41, 191, 82),
]
START_Z = 4
MAX_Z = 13
CLUSTER_LIMIT = 100        # массив ids в кластере обрезан на 100
TILE_REQUEST_LIMIT = 6000  # общий гард на число tile-запросов за обход

# JSONP-обёртка: callback({...});  → group(1) = JSON внутри.
_JSONP_RE = re.compile(r"^callback\((.*)\);?\s*$", re.DOTALL)


def _base() -> str:
    return settings.FGIS_BASE_URL.rstrip("/")


def parse_jsonp(text: str) -> dict:
    """Снимает JSONP-обёртку `callback( ... );` и парсит JSON.

    Пустой/битый ответ (напр. HTTP 500 при слишком большом bbox) → пустая
    FeatureCollection. Если обёртки нет — пробуем распарсить как чистый JSON.
    """
    s = (text or "").strip()
    if not s:
        return {"type": "FeatureCollection", "features": []}
    m = _JSONP_RE.match(s)
    payload = m.group(1) if m else s
    payload = payload.strip()
    if not payload:
        return {"type": "FeatureCollection", "features": []}
    try:
        return json.loads(payload)
    except (ValueError, TypeError) as e:
        logger.warning("[fgis] не удалось распарсить JSONP: %s", e)
        return {"type": "FeatureCollection", "features": []}


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def split_bbox_2x2(
    bbox: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]:
    """Делит ячейку на 4 равные подъячейки (2×2)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    mid_lon = (min_lon + max_lon) / 2
    mid_lat = (min_lat + max_lat) / 2
    return [
        (min_lon, min_lat, mid_lon, mid_lat),
        (mid_lon, min_lat, max_lon, mid_lat),
        (min_lon, mid_lat, mid_lon, max_lat),
        (mid_lon, mid_lat, max_lon, max_lat),
    ]


# --- Сырые запросы к API -------------------------------------------------------


async def fetch_regions() -> list[dict]:
    """GET filters/regions → [{"id": int, "name": str}, ...] (id = код субъекта)."""
    url = f"{_base()}{MAP_API_PREFIX}/filters/regions"
    try:
        async with httpx.AsyncClient(timeout=FGIS_TIMEOUT) as http_client:
            resp = await http_client.get(url)
    except Exception as e:  # noqa: BLE001 — транспорт → AppError
        raise AppError(
            "FGIS_UNAVAILABLE", f"ФГИС недоступна: {type(e).__name__}", status_code=502
        ) from e
    if resp.status_code != 200:
        raise AppError(
            "FGIS_ERROR",
            f"ФГИС вернула HTTP {resp.status_code} на запросе регионов",
            status_code=502,
        )
    data = resp.json()
    out: list[dict] = []
    for r in data or []:
        rid = r.get("id")
        if rid is None:
            continue
        out.append({"id": int(rid), "name": r.get("name") or ""})
    return out


async def create_filter(region_id: int) -> str:
    """POST map/filter — присланный нами uuid И ЕСТЬ filterId. regionId ограничивает выдачу."""
    filter_id = str(uuid.uuid4())
    url = f"{_base()}{MAP_API_PREFIX}/map/filter"
    body = {"id": filter_id, "layers": [LAYER], "regionId": region_id}
    try:
        async with httpx.AsyncClient(timeout=FGIS_TIMEOUT) as http_client:
            resp = await http_client.post(url, json=body)
    except Exception as e:  # noqa: BLE001
        raise AppError(
            "FGIS_UNAVAILABLE", f"ФГИС недоступна: {type(e).__name__}", status_code=502
        ) from e
    if resp.status_code != 200:
        raise AppError(
            "FGIS_ERROR",
            f"ФГИС вернула HTTP {resp.status_code} на создании фильтра",
            status_code=502,
        )
    return filter_id


async def region_center(region_id: int) -> list[float]:
    """GET map/region/{id}/center → [lon, lat]."""
    url = f"{_base()}{MAP_API_PREFIX}/map/region/{region_id}/center"
    try:
        async with httpx.AsyncClient(timeout=FGIS_TIMEOUT) as http_client:
            resp = await http_client.get(url)
    except Exception as e:  # noqa: BLE001
        raise AppError(
            "FGIS_UNAVAILABLE", f"ФГИС недоступна: {type(e).__name__}", status_code=502
        ) from e
    if resp.status_code != 200:
        raise AppError(
            "FGIS_ERROR",
            f"ФГИС вернула HTTP {resp.status_code} на центре региона",
            status_code=502,
        )
    data = resp.json()
    return [float(data[0]), float(data[1])]


async def fetch_tile(
    filter_id: str, bbox: tuple[float, float, float, float], z: int
) -> list[dict]:
    """GET map/tile → features из JSONP.

    Устойчив к HTTP 500 (слишком большой bbox для зума): вернёт [] и залогирует —
    обход продолжается.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    params = {
        "bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}",
        "z": z,
        "filterId": filter_id,
    }
    url = f"{_base()}{MAP_API_PREFIX}/map/tile"
    try:
        async with httpx.AsyncClient(timeout=FGIS_TIMEOUT) as http_client:
            resp = await http_client.get(url, params=params)
    except Exception as e:  # noqa: BLE001 — сетевой сбой одной ячейки не роняет обход
        logger.warning("[fgis] tile сбой %s bbox=%s z=%s", type(e).__name__, bbox, z)
        return []
    if resp.status_code != 200:
        logger.warning("[fgis] tile non-200: %s bbox=%s z=%s", resp.status_code, bbox, z)
        return []
    data = parse_jsonp(resp.text)
    return data.get("features") or []


async def cluster_details(ids: list[str], region_id: int) -> list[dict]:
    """POST sidebar/cluster → полные данные объектов (name/address/area/location/...)."""
    if not ids:
        return []
    url = f"{_base()}{MAP_API_PREFIX}/sidebar/cluster"
    body = {"ids": list(ids), "layer": LAYER, "regionId": region_id}
    try:
        async with httpx.AsyncClient(timeout=FGIS_TIMEOUT) as http_client:
            resp = await http_client.post(url, json=body)
    except Exception as e:  # noqa: BLE001
        raise AppError(
            "FGIS_UNAVAILABLE", f"ФГИС недоступна: {type(e).__name__}", status_code=502
        ) from e
    if resp.status_code != 200:
        raise AppError(
            "FGIS_ERROR",
            f"ФГИС вернула HTTP {resp.status_code} на деталях кластера",
            status_code=502,
        )
    data = resp.json()
    return data if isinstance(data, list) else []


# --- Краулер: перечислить все id МНО региона -----------------------------------


async def enumerate_region_mno_ids(
    filter_id: str,
    region_id: int,
    *,
    on_progress: Callable[[int], None] | None = None,
) -> tuple[set[str], list[str]]:
    """Обходит карту региона (BFS по ячейкам) и собирает set всех id МНО.

    Правила разбора фичи тайла:
      - одиночный объект (есть "id", нет "ids") → добавить id;
      - кластер ("ids" + "iconContent"=полное число):
          * iconContent <= 100 → массив ids полный, добавить все;
          * иначе, если z >= MAX_Z → фолбэк: взять обрезанные ids (объекты в одной
            точке, дальше дробить бессмысленно);
          * иначе → раздробить ячейку 2×2 и поставить в очередь с зумом +2.
    Гард TILE_REQUEST_LIMIT прерывает обход и пишет причину в issues.

    Возвращает (ids_set, issues) — issues пуст при штатном обходе.
    """
    from collections import deque

    ids_set: set[str] = set()
    issues: list[str] = []
    truncated = 0
    tile_requests = 0

    queue: deque[tuple[tuple[float, float, float, float], int]] = deque(
        (cell, START_Z) for cell in START_CELLS
    )

    while queue:
        if tile_requests >= TILE_REQUEST_LIMIT:
            issues.append(
                f"достигнут лимит tile-запросов ({TILE_REQUEST_LIMIT}) — обход прерван, "
                "часть МНО могла не попасть в выборку"
            )
            break
        bbox, z = queue.popleft()
        tile_requests += 1
        features = await fetch_tile(filter_id, bbox, z)
        for f in features:
            p = f.get("properties") or {}
            if "ids" in p:  # кластер
                total = _safe_int(p.get("iconContent"))
                if total <= CLUSTER_LIMIT:
                    ids_set.update(p.get("ids") or [])
                elif z >= MAX_Z:
                    ids_set.update(p.get("ids") or [])
                    truncated += 1
                else:
                    next_z = min(z + 2, MAX_Z)
                    for sub in split_bbox_2x2(bbox):
                        queue.append((sub, next_z))
            else:  # одиночный объект
                pid = p.get("id")
                if pid:
                    ids_set.add(pid)
        if on_progress is not None:
            on_progress(len(ids_set))

    if truncated:
        issues.append(
            f"на максимальном зуме {truncated} кластер(ов) с >100 объектами — взяты "
            "первые 100 (совпадающие координаты)"
        )
    return ids_set, issues
