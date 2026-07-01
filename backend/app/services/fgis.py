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
from collections.abc import Awaitable, Callable

import httpx

from ..config import settings
from ..core.errors import AppError

logger = logging.getLogger(__name__)

# --- Константы API -------------------------------------------------------------

MAP_API_PREFIX = "/reo-fs-public-map-api/api/v2.0"
LAYER = 5  # слой «места накопления отходов»
FGIS_TIMEOUT = 40

# --- Константы обхода (краулер) ------------------------------------------------

# Стартовые ячейки покрывают РФ колонками ~40° по долготе при START_Z=4.
# Региональный фильтр => в нерелевантных ячейках фич просто нет.
# ВАЖНО: API отдаёт 500 на ЛЮБОЙ bbox за 180° (антимеридиан), поэтому восток обрезан
# на 180° — крайние точки Чукотки за 180° API всё равно не отдаёт (проверено curl).
START_CELLS: list[tuple[float, float, float, float]] = [
    (19, 41, 62, 82),
    (62, 41, 105, 82),
    (105, 41, 148, 82),
    (148, 41, 180, 82),
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


async def sidebar_object(mno_id: str) -> dict | None:
    """GET sidebar/object — публично ДОКУМЕНТИРОВАННЫЙ метод (док ФГИС §3): сведения о МНО
    по ОДНОМУ id. Фолбэк для cluster_details, если батч-метод sidebar/cluster (его нет в
    публичной доке) окажется недоступен. Возвращает ВЛОЖЕННУЮ форму
    {..., location:{coordinates:{latitude,longitude}, areaName, populationName, address}}.
    Сбой одного id → None (не роняет обход)."""
    url = f"{_base()}{MAP_API_PREFIX}/sidebar/object"
    params = {"Id": mno_id, "Layer": LAYER}
    try:
        async with httpx.AsyncClient(timeout=FGIS_TIMEOUT) as http_client:
            resp = await http_client.get(url, params=params)
    except Exception:  # noqa: BLE001 — фолбэк, сбой одного id не критичен
        return None
    if resp.status_code != 200:
        return None
    try:
        obj = resp.json()
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _object_to_flat(o: dict) -> dict:
    """Приводит ВЛОЖЕННЫЙ ответ sidebar/object (док §3) к ПЛОСКОЙ форме sidebar/cluster,
    чтобы upsert читал детали единообразно независимо от источника."""
    loc = o.get("location") or {}
    coords = loc.get("coordinates") or {}
    return {
        "id": o.get("id"),
        "name": o.get("name") or "",
        "registryNumber": o.get("registryNumber") or "",
        "area": loc.get("areaName") or "",
        "population": loc.get("populationName") or "",
        "address": loc.get("address") or "",
        "location": {
            "latitude": coords.get("latitude"),
            "longitude": coords.get("longitude"),
        },
    }


async def cluster_details(ids: list[str], region_id: int) -> list[dict]:
    """Детали МНО батчем. Основной путь — POST sidebar/cluster (быстро, до 100 id/запрос).

    Если батч-метод недоступен (сеть/не-200) — деградируем на публично документированный
    sidebar/object по одному id (док §3), приводя его к той же плоской форме. Так
    синхронизация остаётся живой и doc-совместимой, если ФГИС когда-нибудь прикроет батч.
    Плоская форма: {id,name,registryNumber,area,population,address,location:{latitude,longitude}}.
    """
    if not ids:
        return []
    url = f"{_base()}{MAP_API_PREFIX}/sidebar/cluster"
    body = {"ids": list(ids), "layer": LAYER, "regionId": region_id}
    try:
        async with httpx.AsyncClient(timeout=FGIS_TIMEOUT) as http_client:
            resp = await http_client.post(url, json=body)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
        logger.warning(
            "[fgis] sidebar/cluster HTTP %s — фолбэк на sidebar/object (%d id)",
            resp.status_code, len(ids),
        )
    except Exception as e:  # noqa: BLE001 — переходим на документированный фолбэк
        logger.warning(
            "[fgis] sidebar/cluster сбой %s — фолбэк на sidebar/object (%d id)",
            type(e).__name__, len(ids),
        )

    out: list[dict] = []
    for mno_id in ids:
        obj = await sidebar_object(mno_id)
        if obj is not None:
            out.append(_object_to_flat(obj))
    return out


# --- Краулер: перечислить все id МНО региона -----------------------------------


async def enumerate_region_mno_ids(
    filter_id: str,
    region_id: int,
    *,
    on_progress: Callable[[int], None] | None = None,
    on_batch: Callable[[list[str]], Awaitable[None]] | None = None,
    batch_size: int = CLUSTER_LIMIT,
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

    Потоковая запись (on_batch):
      Если передан ``on_batch`` — как только очередь НОВЫХ id накопит ``batch_size``,
      обход НЕ дожидается конца региона, а сразу отдаёт батч через ``await on_batch(...)``
      (вызывающий тянет детали + пишет в БД + commit). Остаток сливается финальным
      вызовом по завершении. Без ``on_batch`` поведение прежнее: собрать полный set и
      вернуть, ничего не флашя (обратная совместимость).

    Возвращает (seen, issues) — issues пуст при штатном обходе.
    """
    from collections import deque

    seen: set[str] = set()          # все встреченные id (итоговый набор)
    pending: list[str] = []         # НОВЫЕ id, ещё не отданные в on_batch
    issues: list[str] = []
    truncated = 0
    tile_requests = 0

    def _add(pid: str | None) -> None:
        """Регистрирует НОВЫЙ id: в общий set seen и в очередь pending на потоковый флаш."""
        if pid and pid not in seen:
            seen.add(pid)
            pending.append(pid)

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
                    for cid in p.get("ids") or []:
                        _add(cid)
                elif z >= MAX_Z:
                    for cid in p.get("ids") or []:
                        _add(cid)
                    truncated += 1
                else:
                    next_z = min(z + 2, MAX_Z)
                    for sub in split_bbox_2x2(bbox):
                        queue.append((sub, next_z))
            else:  # одиночный объект
                _add(p.get("id"))
        if on_progress is not None:
            on_progress(len(seen))
        # Потоковый флаш: пока накоплено >= batch_size новых id — сразу отдаём батч,
        # не дожидаясь конца обхода региона (данные копятся непрерывно, переживают обрыв).
        if on_batch is not None:
            while len(pending) >= batch_size:
                await on_batch(pending[:batch_size])
                del pending[:batch_size]

    # Слить остаток (последний неполный батч).
    if on_batch is not None and pending:
        await on_batch(pending)
        pending.clear()

    if truncated:
        issues.append(
            f"на максимальном зуме {truncated} кластер(ов) с >100 объектами — взяты "
            "первые 100 (совпадающие координаты)"
        )
    return seen, issues
