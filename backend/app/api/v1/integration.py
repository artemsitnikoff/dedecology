"""Эндпоинты раздела «Интеграция ФГИС» (ТОЛЬКО супер-админ).

Монтируется в router.py с dependencies=[Depends(require_superadmin)] — гвард роли
на уровне включения роутера. Вне мобильного API.

Порядок роутов: статических коллизий нет (нет path-параметров, только /overview,
/regions/sync, /mno/sync, /mno/sync/status).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.errors import AppError
from ...database import get_db
from ...models import Region
from ...schemas.integration import (
    IntegrationOverview,
    MnoSyncRequest,
    MnoSyncStartResult,
    MnoSyncStatus,
    RegionsSyncResult,
)
from ...services import mno_sync

router = APIRouter()

TAG = "Интеграция ФГИС (супер-админ)"


@router.get("/overview", response_model=IntegrationOverview, tags=[TAG])
async def get_overview(session: AsyncSession = Depends(get_db)):
    """Сводка: регионы (всего + посл. синхронизация), МНО (всего), разбивка по регионам."""
    return await mno_sync.overview(session)


@router.post("/regions/sync", response_model=RegionsSyncResult, tags=[TAG])
async def sync_regions(session: AsyncSession = Depends(get_db)):
    """Синхронно тянет справочник субъектов РФ из ФГИС и upsert-ит его в БД."""
    result = await mno_sync.sync_regions(session)
    await session.commit()
    return result


@router.post("/mno/sync", response_model=MnoSyncStartResult, tags=[TAG])
async def start_mno_sync(
    payload: MnoSyncRequest,
    session: AsyncSession = Depends(get_db),
):
    """Запускает ФОНОВУЮ синхронизацию МНО региона. Если уже идёт — возвращает её.

    Регион должен быть в справочнике (иначе 404 — сначала синхронизируй регионы).
    """
    region = await mno_sync.get_region_or_404(session, payload.region_code)
    job = mno_sync.start_mno_sync(region.code, region.name)
    return MnoSyncStartResult(
        job_id=job.job_id, region_code=job.region_code, state=job.state
    )


@router.post("/mno/sync-all", response_model=MnoSyncStartResult, tags=[TAG])
async def start_mno_sync_all(session: AsyncSession = Depends(get_db)):
    """Запуск ФОНОВОЙ синхронизации МНО по ВСЕМ регионам справочника (последовательно).

    Обходит субъекты по алфавиту одной задачей с общим прогрессом. Если такой прогон
    уже идёт — возвращает его. Пустой справочник → 400 (сначала синхронизируй регионы).
    """
    rows = (
        await session.execute(
            select(Region.code, Region.name).order_by(Region.name)
        )
    ).all()
    if not rows:
        raise AppError(
            "NO_REGIONS",
            "Справочник регионов пуст — сначала синхронизируйте регионы",
            status_code=400,
        )
    job = mno_sync.start_mno_sync_all([(c, n) for c, n in rows])
    return MnoSyncStartResult(
        job_id=job.job_id, region_code=job.region_code, state=job.state
    )


@router.get("/mno/sync/status", response_model=MnoSyncStatus, tags=[TAG])
async def mno_sync_status(
    job_id: str | None = Query(None),
    region_code: str | None = Query(None),
):
    """Прогресс/итог фоновой синхронизации по job_id ИЛИ по region_code (последняя задача)."""
    job = None
    if job_id:
        job = mno_sync.get_job(job_id)
    elif region_code:
        job = mno_sync.get_region_job(region_code)

    if job is None:
        raise AppError(
            "NOT_FOUND", "Задача синхронизации не найдена", status_code=404
        )
    return mno_sync.job_to_status(job)
