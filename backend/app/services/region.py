"""Справочник «Регионы»: список с подсчётами, карточка, создание.

mno_count — число МНО региона (по region_code). incidents_count — число обращений,
у которых Incident.region совпадает с Region.name (привязка по ИМЕНИ, как в прототипе).
"""

import uuid

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import ConflictError, NotFoundError
from ..models import Incident, Mno, Region
from ..schemas.region import RegionDetail, RegionListItem
from .addr_norm import normalize_region, region_match_key
from .audit import audit
from .federal_districts import fed_code, fed_name

# sort-ключи, считаемые в Python (mno/inc — вычисляемые, поэтому сортируем после сбора)
_SORT_KEYS = {"code", "name", "fed", "operator", "mno", "inc"}


def _filters(search: str | None, fed: list[int] | None) -> list:
    filters: list = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        # operators — JSONB; приводим к тексту, чтобы искать по именам операторов.
        filters.append(
            or_(
                Region.code.ilike(term),
                Region.name.ilike(term),
                cast(Region.operators, Text).ilike(term),
            )
        )
    if fed:
        filters.append(Region.fed.in_(fed))
    return filters


async def _mno_counts(session: AsyncSession) -> dict[str, int]:
    """region_code → число МНО."""
    result = await session.execute(
        select(Mno.region_code, func.count(Mno.id)).group_by(Mno.region_code)
    )
    return {code: cnt for code, cnt in result.all()}


async def _incident_counts(session: AsyncSession) -> dict[str, int]:
    """region (имя) → число обращений."""
    result = await session.execute(
        select(Incident.region, func.count(Incident.id)).group_by(Incident.region)
    )
    return {name: cnt for name, cnt in result.all()}


def _to_list_item(
    r: Region, mno_counts: dict[str, int], inc_counts: dict[str, int]
) -> RegionListItem:
    return RegionListItem(
        code=r.code,
        name=r.name,
        fed=r.fed,
        fed_code=fed_code(r.fed),
        fed_name=fed_name(r.fed),
        operators=list(r.operators or []),
        active=r.active,
        last_sync=r.last_sync,
        mno_count=mno_counts.get(r.code, 0),
        incidents_count=inc_counts.get(r.name, 0),
    )


def _sort_items(items: list[RegionListItem], sort: str, order: str) -> list[RegionListItem]:
    reverse = order == "desc"
    if sort == "name":
        key = lambda x: x.name
    elif sort == "fed":
        key = lambda x: x.fed
    elif sort == "operator":
        key = lambda x: (x.operators[0] if x.operators else "")
    elif sort == "mno":
        key = lambda x: x.mno_count
    elif sort == "inc":
        key = lambda x: x.incidents_count
    else:  # code (default) — числовой код субъекта
        key = lambda x: (int(x.code) if x.code.isdigit() else 0, x.code)
    return sorted(items, key=key, reverse=reverse)


async def list_regions(
    session: AsyncSession,
    *,
    search: str | None = None,
    fed: list[int] | None = None,
    sort: str = "code",
    order: str = "asc",
) -> list[RegionListItem]:
    """Справочник регионов с фильтрами search/fed + сортировкой (вкл. вычисляемые поля)."""
    filters = _filters(search, fed)
    stmt = select(Region)
    if filters:
        stmt = stmt.where(*filters)
    rows = (await session.execute(stmt)).scalars().all()

    mno_counts = await _mno_counts(session)
    inc_counts = await _incident_counts(session)
    items = [_to_list_item(r, mno_counts, inc_counts) for r in rows]
    return _sort_items(items, sort, order)


async def canonical_index(session: AsyncSession) -> dict[str, str]:
    """{ключ сопоставления → каноническое ``Region.name``} по всему справочнику.

    Для УТКО-выгрузки: имя субъекта в инциденте — свободный текст DaData/AI, а УТКО
    принимает ТОЛЬКО имена из справочника (он синхронизирован из ФГИС и уже содержит
    правильные формы: «г. Санкт-Петербург», «Кемеровская область - Кузбасс»). Индекс
    позволяет привести текст инцидента к канону, когда МНО у инцидента нет.

    ``normalize_region`` применяется к именам справочника — и к искомому значению у
    вызывающего; функция идемпотентна, поэтому обе стороны приводятся одинаково.
    """
    names = (await session.execute(select(Region.name))).scalars().all()
    return {region_match_key(normalize_region(n)): n for n in names if n}


async def get_region(session: AsyncSession, code: str) -> RegionDetail:
    """Карточка региона по коду субъекта."""
    result = await session.execute(select(Region).where(Region.code == code))
    region = result.scalar_one_or_none()
    if region is None:
        raise NotFoundError("Регион")
    mno_counts = await _mno_counts(session)
    inc_counts = await _incident_counts(session)
    item = _to_list_item(region, mno_counts, inc_counts)
    return RegionDetail(**item.model_dump())


async def create_region(session: AsyncSession, data, actor_user_id: uuid.UUID) -> RegionDetail:
    """Создаёт регион: active=True. Дубликат code → 409. Аудит — на создание."""
    code = data.code.strip()
    existing = (
        await session.execute(select(Region).where(Region.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"Регион с кодом {code} уже есть в справочнике")

    region = Region(
        code=code,
        name=data.name.strip(),
        fed=data.fed,
        operators=list(data.operators or []),
        active=True,
        last_sync=None,
    )
    session.add(region)
    await session.flush()
    await audit(
        session,
        action="create",
        entity_type="region",
        entity_id=region.id,
        after={
            "code": region.code,
            "name": region.name,
            "fed": region.fed,
            "operators": region.operators,
            "active": region.active,
        },
        actor_user_id=actor_user_id,
    )
    item = _to_list_item(region, await _mno_counts(session), await _incident_counts(session))
    return RegionDetail(**item.model_dump())
