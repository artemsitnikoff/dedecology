"""Эндпоинты раздела «Интеграция ФГИС» (ТОЛЬКО супер-админ).

Монтируется в router.py с dependencies=[Depends(require_superadmin)] — гвард роли
на уровне включения роутера. Вне мобильного API.

Фоновая синхронизация МНО кладётся в очередь arq (enqueue), исполняет её отдельный
процесс (app.worker). Прогресс/состояние — в Redis (app.services.mno_jobs), общее для
всех uvicorn-воркеров: опрос статуса из любого воркера видит одну и ту же задачу.
Если Redis/очередь недоступны (пул не поднялся на старте) — запуск честно отдаёт 503,
а не 500. Порядок роутов: статических коллизий нет (нет path-параметров).
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.errors import AppError
from ...database import get_db
from ...models import Region
from ...redis_client import get_redis
from ...schemas.integration import (
    IntegrationOverview,
    MnoCancelRequest,
    MnoCancelResult,
    MnoSyncRequest,
    MnoSyncStartResult,
    MnoSyncStatus,
    RegionsSyncResult,
)
from ...services import mno_jobs, mno_sync

router = APIRouter()

TAG = "Интеграция ФГИС (супер-админ)"

ALL_JOB_KEY = "__all__"  # ключ прогона «все регионы» (region_code + ptr)


def _get_pool(request: Request):
    """arq-пул из app.state (поднят в lifespan). None → Redis/очередь недоступны → 503."""
    pool = getattr(request.app.state, "arq_pool", None)
    if pool is None:
        raise AppError(
            "QUEUE_UNAVAILABLE",
            "Очередь недоступна (Redis)",
            status_code=503,
        )
    return pool


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
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Ставит в очередь ФОНОВУЮ синхронизацию МНО региона. Если уже идёт — возвращает её.

    Регион должен быть в справочнике (иначе 404 — сначала синхронизируй регионы).
    Очередь недоступна (Redis лежит) → 503 QUEUE_UNAVAILABLE.
    """
    region = await mno_sync.get_region_or_404(session, payload.region_code)
    pool = _get_pool(request)
    redis = get_redis()

    # Дедуп: если по региону уже идёт задача — возвращаем её, новую не плодим.
    running = await mno_jobs.get_running_job(redis, region.code)
    if running is not None:
        return MnoSyncStartResult(
            job_id=running["job_id"],
            region_code=running["region_code"],
            state=running["state"],
        )

    job_id = str(uuid4())
    prog = mno_jobs.initial_progress(
        job_id, region.code, region.name, scope="region", regions_total=1
    )
    prog["current_region"] = region.name
    await mno_jobs.write_progress(redis, job_id, prog)
    await mno_jobs.set_pointer(redis, region.code, job_id)
    await pool.enqueue_job("sync_region_task", job_id, region.code, region.name)
    return MnoSyncStartResult(job_id=job_id, region_code=region.code, state="running")


@router.post("/mno/sync-all", response_model=MnoSyncStartResult, tags=[TAG])
async def start_mno_sync_all(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Ставит в очередь ФОНОВУЮ синхронизацию МНО по ВСЕМ регионам справочника (одной задачей).

    Обходит субъекты по алфавиту. Если такой прогон уже идёт — возвращает его. Пустой
    справочник → 400 (сначала синхронизируй регионы). Очередь недоступна → 503.
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

    pool = _get_pool(request)
    redis = get_redis()

    # Дедуп по ключу «все регионы».
    running = await mno_jobs.get_running_job(redis, ALL_JOB_KEY)
    if running is not None:
        return MnoSyncStartResult(
            job_id=running["job_id"],
            region_code=running["region_code"],
            state=running["state"],
        )

    job_id = str(uuid4())
    prog = mno_jobs.initial_progress(
        job_id, ALL_JOB_KEY, "Все регионы", scope="all", regions_total=len(rows)
    )
    await mno_jobs.write_progress(redis, job_id, prog)
    await mno_jobs.set_pointer(redis, ALL_JOB_KEY, job_id)
    await pool.enqueue_job(
        "sync_all_task", job_id, [[code, name] for code, name in rows]
    )
    return MnoSyncStartResult(job_id=job_id, region_code=ALL_JOB_KEY, state="running")


@router.post("/mno/sync/cancel", response_model=MnoCancelResult, tags=[TAG])
async def cancel_mno_sync(payload: MnoCancelRequest):
    """Отменяет идущую фоновую синхронизацию МНО и СРАЗУ разблокирует запуск в UI.

    scope="all" → прогон «все регионы» (ключ "__all__"); иначе scope трактуется как
    region_code. Ставит cancel-флаг (воркер прекратит краул на ближайшем батче), сразу
    метит снимок state="cancelled" (статус отражает отмену без ожидания воркера) и СНИМАЕТ
    указатель → get_running_job=None, кнопка запуска снова активна. Если активной задачи
    по ключу нет — cancelled=false (отменять было нечего), без ошибки.
    """
    redis = get_redis()
    key = ALL_JOB_KEY if payload.scope == "all" else payload.scope
    job_id = await mno_jobs.get_pointer(redis, key)
    if job_id:
        await mno_jobs.set_cancelled(redis, job_id)
        # Немедленно отражаем отмену в снимке, чтобы опрос статуса увидел её сразу.
        prog = await mno_jobs.read_progress(redis, job_id)
        if prog is not None:
            prog["state"] = "cancelled"
            prog["finished_at"] = mno_jobs.utcnow()
            await mno_jobs.write_progress(redis, job_id, prog)
    # Снимаем указатель в любом случае — залипшая (running) задача перестаёт блокировать UI.
    await mno_jobs.clear_job(redis, key, job_id)
    return MnoCancelResult(cancelled=bool(job_id), job_id=job_id)


@router.get("/mno/sync/status", response_model=MnoSyncStatus, tags=[TAG])
async def mno_sync_status(
    job_id: str | None = Query(None),
    region_code: str | None = Query(None),
):
    """Прогресс/итог фоновой синхронизации по job_id ИЛИ по region_code (последняя задача).

    Состояние читается из Redis, поэтому видно из любого uvicorn-воркера.
    """
    redis = get_redis()
    prog = None
    if job_id:
        prog = await mno_jobs.read_progress(redis, job_id)
    elif region_code:
        pointed = await mno_jobs.get_pointer(redis, region_code)
        if pointed:
            prog = await mno_jobs.read_progress(redis, pointed)

    if prog is None:
        raise AppError(
            "NOT_FOUND", "Задача синхронизации не найдена", status_code=404
        )
    return MnoSyncStatus(**prog)
