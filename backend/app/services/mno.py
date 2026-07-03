"""МНО (места накопления отходов): список+фильтры, карточка, создание, синхронизация.

ВАЖНО про синхронизацию с ФГИС: реальной интеграции с ФГИС УТКО НЕТ. sync_all/sync_one —
ЛОКАЛЬНАЯ ЗАГЛУШКА: помечают МНО как synced и проставляют placeholder-fgis_id вида
"STUB-xxxxxxxx". Никакие внешние запросы не выполняются. Когда появится боевая интеграция —
заглушка заменяется реальным клиентом ФГИС.
"""

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import NotFoundError
from ..models import Mno, Region
from ..schemas.base import Paginated
from ..schemas.mno import (
    MnoDetail,
    MnoFormPoint,
    MnoFormPointsResponse,
    MnoListItem,
    MnoPoint,
    MnoPointsResponse,
    MnoSyncResult,
)
from .audit import audit
from .geo import parse_bbox, parse_latlon

# Максимум точек, отдаваемых карте за КАДР (bbox) или глобально (карта не грузит весь реестр).
MAX_POINTS = 2000

# Потолок точек МНО для ПУБЛИЧНОЙ формы (карта выбора площадки): меньше админ-карты —
# неавторизованный эндпоинт, кадр формы обычно узкий (позиция пользователя/улица).
FORM_MAX_POINTS = 500

# sort-ключ из API → колонка модели. region сортируется по коду субъекта.
_SORT_COLUMNS = {
    "name": Mno.name,
    "reg": Mno.reg,
    "region": Mno.region_code,
    "city": Mno.city,
    "address": Mno.address,
    "coords": Mno.coords,
}


def _search_clause(search: str):
    """ilike-OR по name/reg/city/address/coords/fgis_id."""
    term = f"%{search.strip()}%"
    return or_(
        Mno.name.ilike(term),
        Mno.reg.ilike(term),
        Mno.city.ilike(term),
        Mno.address.ilike(term),
        Mno.coords.ilike(term),
        Mno.fgis_id.ilike(term),
    )


def _filters(search: str | None, region: str | None, synced: bool | None) -> list:
    filters: list = []
    if search and search.strip():
        filters.append(_search_clause(search))
    if region and region.strip():
        filters.append(Mno.region_code == region.strip())
    if synced is not None:
        filters.append(Mno.synced.is_(synced))
    return filters


async def _region_names(session: AsyncSession) -> dict[str, str]:
    """code → name по справочнику регионов (для region_name в выдаче)."""
    result = await session.execute(select(Region.code, Region.name))
    return {code: name for code, name in result.all()}


def _to_list_item(m: Mno, region_names: dict[str, str]) -> MnoListItem:
    return MnoListItem(
        id=m.id,
        reg=m.reg,
        name=m.name,
        region_code=m.region_code,
        region_name=region_names.get(m.region_code, m.region_code),
        city=m.city,
        address=m.address,
        coords=m.coords,
        fgis_id=m.fgis_id,
        synced=m.synced,
        sync_date=m.sync_date,
        incidents=m.incidents,
    )


async def _count(
    session: AsyncSession,
    *,
    search: str | None,
    region: str | None,
    synced: bool | None,
) -> int:
    """COUNT(*) по тем же фильтрам, что и список (для пагинации/карты)."""
    filters = _filters(search, region, synced)
    stmt = select(func.count(Mno.id))
    if filters:
        stmt = stmt.where(*filters)
    return (await session.execute(stmt)).scalar_one()


async def _query(
    session: AsyncSession,
    *,
    search: str | None,
    region: str | None,
    synced: bool | None,
    sort: str,
    order: str,
    offset: int | None = None,
    limit: int | None = None,
) -> list[Mno]:
    """Ядро фильтра/сортировки: сырые строки Mno.

    offset/limit опциональны — None означает «весь набор» (используется экспортом).
    """
    filters = _filters(search, region, synced)
    stmt = select(Mno)
    if filters:
        stmt = stmt.where(*filters)
    sort_col = _SORT_COLUMNS.get(sort, Mno.name)
    direction = asc if order == "asc" else desc
    stmt = stmt.order_by(direction(sort_col), direction(Mno.id))
    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_mno(
    session: AsyncSession,
    *,
    search: str | None = None,
    region: str | None = None,
    synced: bool | None = None,
    sort: str = "name",
    order: str = "asc",
    page: int = 1,
    page_size: int = 100,
) -> Paginated[MnoListItem]:
    """Пагинированный реестр МНО с фильтрами region/synced/search + сортировкой."""
    total = await _count(session, search=search, region=region, synced=synced)
    rows = await _query(
        session,
        search=search,
        region=region,
        synced=synced,
        sort=sort,
        order=order,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    region_names = await _region_names(session)
    items = [_to_list_item(m, region_names) for m in rows]
    pages = math.ceil(total / page_size) if total > 0 else 0
    return Paginated[MnoListItem](
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


async def list_for_export(
    session: AsyncSession,
    *,
    search: str | None = None,
    region: str | None = None,
    synced: bool | None = None,
    sort: str = "name",
    order: str = "asc",
) -> list[MnoListItem]:
    """Полный отфильтрованный реестр для .xlsx (БЕЗ пагинации — весь набор)."""
    rows = await _query(
        session, search=search, region=region, synced=synced, sort=sort, order=order
    )
    region_names = await _region_names(session)
    return [_to_list_item(m, region_names) for m in rows]


async def list_points(
    session: AsyncSession,
    *,
    search: str | None = None,
    region: str | None = None,
    synced: bool | None = None,
    bbox: str | None = None,
) -> MnoPointsResponse:
    """Лёгкие координаты МНО для карты: те же фильтры, без имён регионов.

    bbox («minLat,minLon,maxLat,maxLon») — видимая область карты: при зуме/панораме
    фронт перезапрашивает точки текущего кадра, так постепенно виден весь регион.
      - bbox задан и валиден → фильтр по числовым lat/lon (индекс ix_mno_lat_lon) +
        существующие фильтры; total = COUNT по этому кадру.
      - bbox не задан/битый → прежнее поведение: все МНО по фильтрам с непустыми coords.
    В обоих случаях points — первые MAX_POINTS строк; capped=True — total превысил лимит.
    """
    filters = _filters(search, region, synced)
    box = parse_bbox(bbox)
    if box is not None:
        min_lat, min_lon, max_lat, max_lon = box
        filters.append(Mno.lat.is_not(None))
        filters.append(Mno.lat.between(min_lat, max_lat))
        filters.append(Mno.lon.between(min_lon, max_lon))
        total = (
            await session.execute(select(func.count(Mno.id)).where(*filters))
        ).scalar_one()
    else:
        total = await _count(session, search=search, region=region, synced=synced)
        filters.append(Mno.coords != "")
    stmt = (
        select(Mno.id, Mno.coords, Mno.name)
        .where(*filters)
        .order_by(asc(Mno.id))
        .limit(MAX_POINTS)
    )
    result = await session.execute(stmt)
    points = [
        MnoPoint(id=row.id, coords=row.coords, name=row.name) for row in result.all()
    ]
    return MnoPointsResponse(points=points, total=total, capped=total > MAX_POINTS)


async def list_form_points(
    session: AsyncSession, *, bbox: str | None
) -> MnoFormPointsResponse:
    """Точки МНО в видимой области карты для ПУБЛИЧНОЙ формы выбора площадки.

    Отдаёт reg/address (для подстановки в форму) + coords/name. bbox ОБЯЗАТЕЛЕН:
    без валидного bbox отдаём пусто — не тянем весь реестр в неавторизованный
    эндпоинт (в отличие от админского list_points, который без bbox грузит всё
    по фильтрам). Фильтр по числовым lat/lon (индекс ix_mno_lat_lon), как в
    list_points; total — COUNT по кадру; points — первые FORM_MAX_POINTS;
    capped=True — total превысил лимит (пользователю стоит приблизить карту).
    """
    box = parse_bbox(bbox)
    if box is None:
        # bbox не задан/битый → пусто (без обращения к БД: не тянем весь реестр).
        return MnoFormPointsResponse(points=[], total=0, capped=False)

    min_lat, min_lon, max_lat, max_lon = box
    filters = [
        Mno.lat.is_not(None),
        Mno.lat.between(min_lat, max_lat),
        Mno.lon.between(min_lon, max_lon),
    ]
    total = (
        await session.execute(select(func.count(Mno.id)).where(*filters))
    ).scalar_one()
    stmt = (
        select(Mno.id, Mno.coords, Mno.reg, Mno.address, Mno.name)
        .where(*filters)
        .order_by(asc(Mno.id))
        .limit(FORM_MAX_POINTS)
    )
    result = await session.execute(stmt)
    points = [
        MnoFormPoint(
            id=row.id,
            coords=row.coords,
            reg=row.reg,
            address=row.address,
            name=row.name,
        )
        for row in result.all()
    ]
    return MnoFormPointsResponse(
        points=points, total=total, capped=total > FORM_MAX_POINTS
    )


async def _get(session: AsyncSession, mno_id: uuid.UUID) -> Mno:
    result = await session.execute(select(Mno).where(Mno.id == mno_id))
    mno = result.scalar_one_or_none()
    if mno is None:
        raise NotFoundError("МНО")
    return mno


async def get_mno(session: AsyncSession, mno_id: uuid.UUID) -> MnoDetail:
    """Карточка МНО."""
    mno = await _get(session, mno_id)
    region_names = await _region_names(session)
    item = _to_list_item(mno, region_names)
    return MnoDetail(**item.model_dump())


async def create_mno(session: AsyncSession, data, actor_user_id: uuid.UUID) -> MnoDetail:
    """Создаёт МНО вручную: synced=False, fgis_id=None, incidents=0.

    Появится в ФГИС только после синхронизации (заглушки). Аудит — на создание.
    """
    coords = data.coords.strip()
    # Числовые lat/lon для bbox-фильтра карты (NULL, если coords пусты/невалидны).
    lat, lon = parse_latlon(coords)
    mno = Mno(
        name=data.name.strip(),
        coords=coords,
        lat=lat,
        lon=lon,
        reg=(data.reg or "").strip(),
        region_code=(data.region_code or "").strip(),
        city=(data.city or "").strip(),
        address=(data.address or "").strip(),
        fgis_id=None,
        synced=False,
        sync_date=None,
        incidents=0,
    )
    session.add(mno)
    await session.flush()
    await audit(
        session,
        action="create",
        entity_type="mno",
        entity_id=mno.id,
        after={
            "name": mno.name,
            "reg": mno.reg,
            "region_code": mno.region_code,
            "coords": mno.coords,
            "synced": mno.synced,
        },
        actor_user_id=actor_user_id,
    )
    region_names = await _region_names(session)
    item = _to_list_item(mno, region_names)
    return MnoDetail(**item.model_dump())


def _stub_fgis_id() -> str:
    """Placeholder-идентификатор ФГИС (реальной интеграции нет)."""
    return f"STUB-{uuid.uuid4().hex[:8]}"


def _apply_sync(mno: Mno, now: datetime) -> None:
    """Помечает одно МНО синхронизированным (заглушка): synced + sync_date + fgis_id."""
    mno.synced = True
    mno.sync_date = now
    if not mno.fgis_id:
        mno.fgis_id = _stub_fgis_id()


async def sync_all(session: AsyncSession, actor_user_id: uuid.UUID) -> MnoSyncResult:
    """ЗАГЛУШКА синхронизации с ФГИС: помечает ВСЕ ещё-не-synced МНО.

    Реальной интеграции с ФГИС УТКО НЕТ — внешних запросов не делаем. Каждому
    несинхронизированному МНО проставляем synced=True, sync_date=now и placeholder
    fgis_id ("STUB-…"). Возвращает {synced: сколько помечено, total: всего МНО}.
    Пишет один системный (actor_type='system') аудит-итог.
    """
    now = datetime.now(timezone.utc)
    total = (await session.execute(select(func.count(Mno.id)))).scalar_one()

    result = await session.execute(select(Mno).where(Mno.synced.is_(False)))
    pending = result.scalars().all()
    for mno in pending:
        _apply_sync(mno, now)
    await session.flush()

    await audit(
        session,
        action="fgis_sync_all",
        entity_type="mno",
        entity_id=None,
        after={"synced": len(pending), "total": total},
        actor_user_id=actor_user_id,
        actor_type="system",
    )
    return MnoSyncResult(synced=len(pending), total=total)


async def sync_one(
    session: AsyncSession, mno_id: uuid.UUID, actor_user_id: uuid.UUID
) -> MnoDetail:
    """ЗАГЛУШКА синхронизации одного МНО с ФГИС (без внешних запросов).

    Идемпотентно: уже синхронизированное МНО лишь обновляет sync_date. Аудит — системный.
    """
    mno = await _get(session, mno_id)
    before = {"synced": mno.synced, "fgis_id": mno.fgis_id}
    _apply_sync(mno, datetime.now(timezone.utc))
    await session.flush()
    await audit(
        session,
        action="fgis_sync_one",
        entity_type="mno",
        entity_id=mno.id,
        before=before,
        after={"synced": mno.synced, "fgis_id": mno.fgis_id},
        actor_user_id=actor_user_id,
        actor_type="system",
    )
    region_names = await _region_names(session)
    item = _to_list_item(mno, region_names)
    return MnoDetail(**item.model_dump())
