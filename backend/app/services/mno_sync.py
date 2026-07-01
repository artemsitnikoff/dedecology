"""Оркестрация синхронизации с ФГИС: справочник регионов (синхронно), UPSERT батча
МНО и сводка.

Фоновый краул МНО (перечисление id + детали + запись) вынесен в arq-воркер:
  - реальная работа задач — app.services.mno_worker (run_sync_region/run_sync_all);
  - прогресс/состояние задач — Redis (app.services.mno_jobs), общий для всех
    uvicorn-воркеров, переживает рестарты и умеет возобновляться.
Здесь остаётся ПЕРЕИСПОЛЬЗУЕМОЕ: _upsert_batch (зовёт воркер), справочник регионов и
overview. In-memory реестр задач удалён — он жил в ОДНОМ воркере и ломал опрос статуса
при uvicorn --workers 2.
"""

from datetime import datetime, timezone

from sqlalchemy import asc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import AppError
from ..models import Mno, Region
from ..schemas.integration import (
    IntegrationOverview,
    MnoOverview,
    PerRegionStat,
    RegionsOverview,
    RegionsSyncResult,
)
from . import fgis
from .region_fed import region_fed


# --- UPSERT батча МНО (используется arq-воркером) ------------------------------


async def _upsert_batch(
    session: AsyncSession, region_id: int, objs: list[dict]
) -> int:
    """UPSERT батча объектов ФГИС в таблицу mno по fgis_id (SELECT → update|insert)."""
    now = datetime.now(timezone.utc)
    count = 0
    for o in objs:
        fgis_id = o.get("id")
        if not fgis_id:
            continue
        loc = o.get("location") or {}
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        coords = f"{lat}, {lon}" if lat is not None and lon is not None else ""
        city = str(o.get("area") or o.get("population") or "")
        values = {
            "reg": o.get("registryNumber") or "",
            "name": o.get("name") or "",
            "region_code": str(region_id),
            "city": city,
            "address": o.get("address") or "",
            "coords": coords,
            "synced": True,
            "sync_date": now,
        }

        existing = (
            await session.execute(select(Mno).where(Mno.fgis_id == fgis_id))
        ).scalar_one_or_none()
        if existing is not None:
            for key, val in values.items():
                setattr(existing, key, val)
        else:
            session.add(Mno(fgis_id=fgis_id, incidents=0, **values))
        count += 1

    await session.flush()
    return count


# --- Синхронизация справочника регионов (синхронно) ----------------------------


async def get_region_or_404(session: AsyncSession, region_code: str) -> Region:
    """Регион по коду или AppError 404 (сначала синхронизируй справочник регионов)."""
    code = (region_code or "").strip()
    region = (
        await session.execute(select(Region).where(Region.code == code))
    ).scalar_one_or_none()
    if region is None:
        raise AppError(
            "REGION_NOT_FOUND",
            "Регион не найден в справочнике — сначала синхронизируйте регионы",
            status_code=404,
        )
    return region


async def sync_regions(session: AsyncSession) -> RegionsSyncResult:
    """Синхронизирует справочник регионов из ФГИС (upsert по code = str(id)).

    Обновляет name/fed/last_sync; при существующей строке СОХРАНЯЕТ operators/active
    (их ведёт админ вручную). Новые регионы создаются active=True, operators=[].
    Не коммитит — коммитит роутер.
    """
    regions = await fgis.fetch_regions()
    now = datetime.now(timezone.utc)
    created = 0
    updated = 0

    for r in regions:
        code = str(r["id"])
        name = r.get("name") or ""
        fed = region_fed(code)
        existing = (
            await session.execute(select(Region).where(Region.code == code))
        ).scalar_one_or_none()
        if existing is not None:
            existing.name = name
            existing.fed = fed
            existing.last_sync = now
            # operators / active — НЕ трогаем (ручные поля).
            updated += 1
        else:
            session.add(
                Region(
                    code=code,
                    name=name,
                    fed=fed,
                    operators=[],
                    active=True,
                    last_sync=now,
                )
            )
            created += 1

    await session.flush()
    return RegionsSyncResult(
        total=len(regions), created=created, updated=updated, last_sync=now
    )


# --- Сводка --------------------------------------------------------------------


async def overview(session: AsyncSession) -> IntegrationOverview:
    """GET /integration/overview: сводка по регионам + МНО + разбивка по регионам."""
    regions_total = (
        await session.execute(select(func.count(Region.id)))
    ).scalar_one()
    regions_last_sync = (
        await session.execute(select(func.max(Region.last_sync)))
    ).scalar_one()
    mno_total = (await session.execute(select(func.count(Mno.id)))).scalar_one()

    mno_rows = (
        await session.execute(
            select(Mno.region_code, func.count(Mno.id)).group_by(Mno.region_code)
        )
    ).all()
    mno_counts: dict[str, int] = {code: cnt for code, cnt in mno_rows}

    # Дата последнего КРАУЛА МНО по региону (max Mno.sync_date) — колонка «Посл.
    # синхронизация» в per-region таблице относится к МНО, а не к справочнику регионов.
    mno_sync_rows = (
        await session.execute(
            select(Mno.region_code, func.max(Mno.sync_date)).group_by(Mno.region_code)
        )
    ).all()
    mno_last_sync: dict[str, datetime | None] = {code: ts for code, ts in mno_sync_rows}

    regions = (
        await session.execute(select(Region).order_by(asc(Region.name)))
    ).scalars().all()
    per_region = [
        PerRegionStat(
            code=r.code,
            name=r.name,
            fed=r.fed,
            mno_count=mno_counts.get(r.code, 0),
            last_sync=mno_last_sync.get(r.code),
        )
        for r in regions
    ]

    return IntegrationOverview(
        regions=RegionsOverview(total=regions_total, last_sync=regions_last_sync),
        mno=MnoOverview(total=mno_total),
        per_region=per_region,
    )
