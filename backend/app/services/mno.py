"""МНО (места накопления отходов): список+фильтры, карточка, создание, синхронизация.

ВАЖНО про синхронизацию с ФГИС: реальной интеграции с ФГИС УТКО НЕТ. sync_all/sync_one —
ЛОКАЛЬНАЯ ЗАГЛУШКА: помечают МНО как synced и проставляют placeholder-fgis_id вида
"STUB-xxxxxxxx". Никакие внешние запросы не выполняются. Когда появится боевая интеграция —
заглушка заменяется реальным клиентом ФГИС.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import NotFoundError
from ..models import Mno, Region
from ..schemas.mno import MnoDetail, MnoListItem, MnoSyncResult
from .audit import audit

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


async def _query(
    session: AsyncSession,
    *,
    search: str | None,
    region: str | None,
    synced: bool | None,
    sort: str,
    order: str,
) -> list[Mno]:
    filters = _filters(search, region, synced)
    stmt = select(Mno)
    if filters:
        stmt = stmt.where(*filters)
    sort_col = _SORT_COLUMNS.get(sort, Mno.name)
    direction = asc if order == "asc" else desc
    stmt = stmt.order_by(direction(sort_col), direction(Mno.id))
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
) -> list[MnoListItem]:
    """Список МНО с фильтрами region/synced/search + сортировкой."""
    rows = await _query(
        session, search=search, region=region, synced=synced, sort=sort, order=order
    )
    region_names = await _region_names(session)
    return [_to_list_item(m, region_names) for m in rows]


async def list_for_export(
    session: AsyncSession,
    *,
    search: str | None = None,
    region: str | None = None,
    synced: bool | None = None,
    sort: str = "name",
    order: str = "asc",
) -> list[MnoListItem]:
    """Отфильтрованный реестр для .xlsx (тот же набор, что и список)."""
    return await list_mno(
        session, search=search, region=region, synced=synced, sort=sort, order=order
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
    mno = Mno(
        name=data.name.strip(),
        coords=data.coords.strip(),
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
