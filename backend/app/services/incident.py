"""Инциденты: список+фильтры+сортировка, воронка, карточка, смена статуса (SPEC §3)."""

import math
from datetime import datetime, time, timezone
from uuid import UUID

from sqlalchemy import and_, asc, case, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import NotFoundError, ValidationError
from ..models import Incident
from ..schemas.base import Paginated
from ..schemas.incident import (
    FunnelCounts,
    IncidentListItem,
    IncidentPoint,
    IncidentPointsResponse,
)
from .audit import audit
from .geo import parse_bbox

# Максимум точек инцидентов, отдаваемых карте за КАДР (bbox) или глобально
# (карта не грузит весь реестр).
MAX_POINTS = 3000

# Порядок статусов в БД для сортировки `status` (new < found < none < exported)
_STATUS_ORDER = case(
    (Incident.status == "new", 0),
    (Incident.status == "found", 1),
    (Incident.status == "none", 2),
    (Incident.status == "exported", 3),
    else_=99,
)

# sort-ключ из API → колонка/выражение
_SORT_COLUMNS = {
    "date": Incident.photo_time,
    "time": Incident.photo_time,
    "region": Incident.region,
    "city": Incident.city,
    "address": Incident.street,
    "status": _STATUS_ORDER,
    "source": Incident.source,
}


def _search_clause(search: str):
    """ilike-OR по fio/region/city/street/coords/msg."""
    term = f"%{search.strip()}%"
    return or_(
        Incident.fio.ilike(term),
        Incident.region.ilike(term),
        Incident.city.ilike(term),
        Incident.street.ilike(term),
        Incident.coords.ilike(term),
        Incident.msg.ilike(term),
    )


def _base_filters(
    search: str | None,
    source: list[str] | None,
    date_from: datetime | None,
    date_to: datetime | None,
    region: str | None = None,
    incident_type: str | None = None,
) -> list:
    """Фильтры, общие для списка и воронки (без статуса)."""
    filters: list = []
    if search and search.strip():
        filters.append(_search_clause(search))
    if source:
        filters.append(Incident.source.in_(source))
    # Регион — одиночный, ТОЧНОЕ совпадение (равенство, не ilike). Пусто → не фильтруем.
    if region and region.strip():
        filters.append(Incident.region == region.strip())
    # Тип инцидента — одиночный, ТОЧНОЕ совпадение по коду. Пусто → не фильтруем.
    if incident_type and incident_type.strip():
        filters.append(Incident.incident_type == incident_type.strip())
    # Период по photo_time (НЕ received_at), включительно
    if date_from is not None:
        filters.append(
            Incident.photo_time >= datetime.combine(date_from.date(), time.min, tzinfo=timezone.utc)
        )
    if date_to is not None:
        filters.append(
            Incident.photo_time <= datetime.combine(date_to.date(), time.max, tzinfo=timezone.utc)
        )
    return filters


async def list_incidents(
    session: AsyncSession,
    *,
    search: str | None = None,
    source: list[str] | None = None,
    status: list[str] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    region: str | None = None,
    incident_type: str | None = None,
    sort: str = "date",
    order: str = "desc",
    page: int = 1,
    page_size: int = 100,
) -> Paginated[IncidentListItem]:
    """Список инцидентов с фильтрами/сортировкой/пагинацией."""
    rows = await _query_incidents(
        session,
        search=search,
        source=source,
        status=status,
        date_from=date_from,
        date_to=date_to,
        region=region,
        incident_type=incident_type,
        sort=sort,
        order=order,
        offset=(page - 1) * page_size,
        limit=page_size,
        with_total=True,
    )
    items, total = rows
    pages = math.ceil(total / page_size) if total > 0 else 0
    return Paginated[IncidentListItem](
        items=[IncidentListItem.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


async def _query_incidents(
    session: AsyncSession,
    *,
    search,
    source,
    status,
    date_from,
    date_to,
    sort,
    order,
    offset: int | None,
    limit: int | None,
    with_total: bool,
    region: str | None = None,
    incident_type: str | None = None,
):
    filters = _base_filters(search, source, date_from, date_to, region, incident_type)
    if status:
        filters.append(Incident.status.in_(status))
    where_clause = and_(*filters) if filters else None

    total = 0
    if with_total:
        count_stmt = select(func.count(Incident.id))
        if where_clause is not None:
            count_stmt = count_stmt.where(where_clause)
        total = (await session.execute(count_stmt)).scalar_one()

    sort_col = _SORT_COLUMNS.get(sort, Incident.photo_time)
    direction = asc if order == "asc" else desc
    stmt = select(Incident)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    # Стабильная сортировка: вторичный ключ по id
    stmt = stmt.order_by(direction(sort_col).nulls_last(), direction(Incident.id))
    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    items = result.scalars().all()
    if with_total:
        return items, total
    return items


async def list_for_export(
    session: AsyncSession,
    *,
    search: str | None = None,
    source: list[str] | None = None,
    status: list[str] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    region: str | None = None,
    sort: str = "date",
    order: str = "desc",
) -> list[Incident]:
    """Полный отфильтрованный набор (без пагинации) для GET /export."""
    return await _query_incidents(
        session,
        search=search,
        source=source,
        status=status,
        date_from=date_from,
        date_to=date_to,
        region=region,
        sort=sort,
        order=order,
        offset=None,
        limit=None,
        with_total=False,
    )


async def list_by_ids(session: AsyncSession, ids: list[UUID]) -> list[Incident]:
    """Инциденты по списку id (для POST /export). Сохраняет порядок запроса."""
    if not ids:
        return []
    result = await session.execute(select(Incident).where(Incident.id.in_(ids)))
    by_id = {i.id: i for i in result.scalars().all()}
    return [by_id[i] for i in ids if i in by_id]


async def list_pending_notify(session: AsyncSession, limit: int = 20) -> list[Incident]:
    """Инциденты, ещё не уведомлённые в группу Макс (notified_at IS NULL).

    Сортировка по created_at ASC (старейшие первыми) с лимитом — очередь для
    воркера Макс-бота.
    """
    stmt = (
        select(Incident)
        .where(Incident.notified_at.is_(None), Incident.source == "form")
        .order_by(asc(Incident.created_at), asc(Incident.id))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_notified(session: AsyncSession, ids: list[UUID]) -> int:
    """Помечает инциденты как уведомлённые (notified_at = now(utc)).

    Обновляет только ещё не уведомлённые (notified_at IS NULL) из переданных id —
    идемпотентно. Возвращает число реально обновлённых строк.
    """
    if not ids:
        return 0
    stmt = (
        update(Incident)
        .where(Incident.id.in_(ids), Incident.notified_at.is_(None))
        .values(notified_at=datetime.now(timezone.utc))
    )
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount or 0


async def funnel_counts(
    session: AsyncSession,
    *,
    search: str | None = None,
    source: list[str] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    region: str | None = None,
) -> FunnelCounts:
    """Счётчики чипов воронки. Honor search/source/period/region, НО игнорируют status —
    каждый чип показывает свой потенциальный объём."""
    filters = _base_filters(search, source, date_from, date_to, region)
    where_clause = and_(*filters) if filters else None

    stmt = select(Incident.status, func.count(Incident.id)).group_by(Incident.status)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    result = await session.execute(stmt)

    counts = {"new": 0, "found": 0, "none": 0, "exported": 0}
    total = 0
    for status_value, cnt in result.all():
        total += cnt
        if status_value in counts:
            counts[status_value] = cnt
    return FunnelCounts(all=total, **counts)


async def list_regions(session: AsyncSession) -> list[str]:
    """DISTINCT непустые регионы, отсортированные A→Я (наполняет дропдаун фильтра)."""
    stmt = (
        select(Incident.region)
        .where(Incident.region.is_not(None), Incident.region != "")
        .distinct()
        .order_by(asc(Incident.region))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _short_address(region: str, city: str, street: str) -> str:
    """Краткий адрес для подписи точки на карте: непустые город/улица через запятую.

    Регион на карте избыточен (кластеризация по субъектам и так видна), поэтому в
    подпись идут только город и улица.
    """
    parts = [p.strip() for p in (city, street) if p and p.strip()]
    return ", ".join(parts)


async def list_points(
    session: AsyncSession,
    *,
    search: str | None = None,
    source: list[str] | None = None,
    status: list[str] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    region: str | None = None,
    bbox: str | None = None,
) -> IncidentPointsResponse:
    """Лёгкие координаты инцидентов для карты: те же фильтры, что у списка (без sort/page).

    bbox («minLat,minLon,maxLat,maxLon») — видимая область карты: при зуме/панораме
    фронт перезапрашивает точки текущего кадра, так постепенно виден весь набор.
      - bbox задан и валиден → фильтр по числовым lat/lon (индекс ix_incidents_lat_lon)
        + существующие фильтры; total = COUNT по этому кадру.
      - bbox не задан/битый → прежнее поведение: все инциденты по фильтрам с непустыми coords.
    В обоих случаях points — первые MAX_POINTS строк; capped=True — total превысил лимит.
    """
    filters = _base_filters(search, source, date_from, date_to, region)
    if status:
        filters.append(Incident.status.in_(status))
    box = parse_bbox(bbox)
    if box is not None:
        min_lat, min_lon, max_lat, max_lon = box
        filters.append(Incident.lat.is_not(None))
        filters.append(Incident.lat.between(min_lat, max_lat))
        filters.append(Incident.lon.between(min_lon, max_lon))
    else:
        filters.append(Incident.coords != "")
    where_clause = and_(*filters)

    total = (
        await session.execute(select(func.count(Incident.id)).where(where_clause))
    ).scalar_one()

    stmt = (
        select(
            Incident.id,
            Incident.coords,
            Incident.status,
            Incident.region,
            Incident.city,
            Incident.street,
        )
        .where(where_clause)
        .order_by(asc(Incident.id))
        .limit(MAX_POINTS)
    )
    result = await session.execute(stmt)
    points = [
        IncidentPoint(
            id=row.id,
            coords=row.coords,
            status=row.status,
            address=_short_address(row.region, row.city, row.street),
        )
        for row in result.all()
    ]
    return IncidentPointsResponse(points=points, total=total, capped=total > MAX_POINTS)


async def get_incident(session: AsyncSession, incident_id: UUID) -> Incident:
    result = await session.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if incident is None:
        raise NotFoundError("Инцидент")
    return incident


async def set_status(
    session: AsyncSession,
    incident_id: UUID,
    new_status: str,
    actor_user_id: UUID,
) -> Incident:
    """Смена статуса одного инцидента (PATCH /{id}/status)."""
    incident = await get_incident(session, incident_id)
    before = {"status": incident.status}
    incident.status = new_status
    await session.flush()
    await audit(
        session,
        action="set_status",
        entity_type="incident",
        entity_id=incident.id,
        before=before,
        after={"status": incident.status},
        actor_user_id=actor_user_id,
    )
    return incident


async def bulk_status(
    session: AsyncSession,
    ids: list[UUID],
    new_status: str,
    actor_user_id: UUID,
) -> int:
    """Массовая смена статуса (POST /bulk-status). Возвращает число обновлённых."""
    if not ids:
        return 0

    result = await session.execute(select(Incident).where(Incident.id.in_(ids)))
    incidents = result.scalars().all()

    updated = 0
    for incident in incidents:
        if incident.status == new_status:
            continue
        before = {"status": incident.status}
        incident.status = new_status
        await audit(
            session,
            action="set_status",
            entity_type="incident",
            entity_id=incident.id,
            before=before,
            after={"status": incident.status},
            actor_user_id=actor_user_id,
        )
        updated += 1

    await session.flush()
    return updated


async def bulk_delete(
    session: AsyncSession,
    ids: list[UUID],
    actor_user_id: UUID,
) -> int:
    """Массовое удаление (POST /bulk-delete). Hard delete + audit на каждый.

    No-op-safe: id, которых нет в БД, просто пропускаются. Возвращает число
    реально удалённых строк.
    """
    if not ids:
        return 0

    result = await session.execute(select(Incident).where(Incident.id.in_(ids)))
    incidents = result.scalars().all()

    count = 0
    for incident in incidents:
        await audit(
            session,
            action="delete",
            entity_type="incident",
            entity_id=incident.id,
            before={
                "status": incident.status,
                "source": incident.source,
                "fio": incident.fio,
                "region": incident.region,
                "city": incident.city,
                "street": incident.street,
            },
            actor_user_id=actor_user_id,
        )
        await session.delete(incident)
        count += 1

    await session.flush()
    return count
