"""Оркестрация синхронизации с ФГИС: справочник регионов (синхронно) + фоновый
краулер+детали+upsert МНО по региону.

Реестр фоновых задач — модульный in-memory dict. ВАЖНО: реестр живёт в памяти ОДНОГО
инстанса бэкенда; при рестарте процесса он теряется — это НОРМАЛЬНО (задача не
персистится, повторный запуск синхронизации безопасен и идемпотентен по fgis_id).
Раздел доступен только супер-админу, инстанс один → гонок за словарь нет.
"""

import asyncio
import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import asc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import AppError
from ..database import AsyncSessionLocal
from ..models import Mno, Region
from ..schemas.integration import (
    IntegrationOverview,
    MnoOverview,
    MnoSyncStatus,
    PerRegionStat,
    RegionsOverview,
    RegionsSyncResult,
)
from . import fgis
from .region_fed import region_fed

logger = logging.getLogger(__name__)

UPSERT_BATCH = 100


# --- Реестр фоновых задач ------------------------------------------------------


@dataclass
class MnoSyncJob:
    """Состояние одной фоновой синхронизации МНО региона."""
    job_id: str
    region_code: str
    region_name: str
    state: str = "running"  # running | done | error
    discovered: int = 0
    fetched: int = 0
    upserted: int = 0
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    # Прогон по ВСЕМ регионам (scope="all"): порегионный прогресс. Для одиночной
    # задачи дефолты держат прежнюю семантику (один регион).
    scope: str = "region"          # "region" | "all"
    regions_total: int = 1
    regions_done: int = 0
    regions_failed: int = 0
    current_region: str = ""


# Спец-ключ реестра для задачи «все регионы» (region_code такого прогона).
ALL_JOB_KEY = "__all__"


_jobs: dict[str, MnoSyncJob] = {}          # job_id → задача
_jobs_by_region: dict[str, str] = {}       # region_code → id последней задачи
_running_tasks: set[asyncio.Task] = set()  # держим ссылки, чтобы задачи не собрал GC


def get_job(job_id: str) -> MnoSyncJob | None:
    return _jobs.get(job_id)


def get_region_job(region_code: str) -> MnoSyncJob | None:
    """Последняя задача по региону (или None)."""
    job_id = _jobs_by_region.get(region_code)
    return _jobs.get(job_id) if job_id else None


def job_to_status(job: MnoSyncJob) -> MnoSyncStatus:
    return MnoSyncStatus(
        job_id=job.job_id,
        region_code=job.region_code,
        region_name=job.region_name,
        state=job.state,
        discovered=job.discovered,
        fetched=job.fetched,
        upserted=job.upserted,
        error=job.error,
        started_at=job.started_at,
        finished_at=job.finished_at,
        scope=job.scope,
        regions_total=job.regions_total,
        regions_done=job.regions_done,
        regions_failed=job.regions_failed,
        current_region=job.current_region,
    )


def start_mno_sync(region_code: str, region_name: str) -> MnoSyncJob:
    """Запускает фоновую синхронизацию МНО региона.

    Если по этому region_code задача уже идёт (state == running) — возвращает её,
    новую не плодит.
    """
    existing = get_region_job(region_code)
    if existing is not None and existing.state == "running":
        return existing

    job = MnoSyncJob(
        job_id=str(uuid.uuid4()),
        region_code=region_code,
        region_name=region_name,
    )
    _jobs[job.job_id] = job
    _jobs_by_region[region_code] = job.job_id

    task = asyncio.create_task(_run_mno_sync(job))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return job


# --- Фоновая синхронизация МНО -------------------------------------------------


def _chunks(seq: list, n: int) -> Iterator[list]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


async def _sync_one_region(
    session: AsyncSession, job: MnoSyncJob, region_id: int
) -> None:
    """Общий core одной региональной синхронизации: фильтр → краулер id → батчи
    деталей → upsert. Счётчики job.discovered/fetched/upserted — НАКОПИТЕЛЬНО (+=),
    поэтому хелпер годится и для одиночного региона (base=0 → прежнее поведение), и
    для последовательного прогона по всем регионам (суммирование). DB-сессию отдаёт
    вызывающий."""
    filter_id = await fgis.create_filter(region_id)

    base = job.discovered  # накопленное к началу этого региона

    def _prog(d: int) -> None:
        job.discovered = base + d  # накопительно поверх ранее обнаруженного

    ids_set, issues = await fgis.enumerate_region_mno_ids(
        filter_id, region_id, on_progress=_prog
    )
    job.discovered = base + len(ids_set)
    for issue in issues:
        logger.warning("[mno_sync] регион %s: %s", region_id, issue)

    for batch in _chunks(sorted(ids_set), UPSERT_BATCH):
        objs = await fgis.cluster_details(batch, region_id)
        job.fetched += len(objs)
        job.upserted += await _upsert_batch(session, region_id, objs)
        await session.commit()


async def _run_mno_sync(job: MnoSyncJob) -> None:
    """Фоновая работа одиночного региона: своя DB-сессия, итог как раньше."""
    try:
        async with AsyncSessionLocal() as session:
            await _sync_one_region(session, job, int(job.region_code))

        job.state = "done"
        job.finished_at = datetime.now(timezone.utc)
        logger.info(
            "[mno_sync] регион %s готов: обнаружено=%s детали=%s записано=%s",
            job.region_code, job.discovered, job.fetched, job.upserted,
        )
    except Exception as e:  # noqa: BLE001 — честно фиксируем ошибку в задаче
        job.state = "error"
        job.error = str(e)
        job.finished_at = datetime.now(timezone.utc)
        logger.exception("[mno_sync] регион %s: сбой синхронизации", job.region_code)


async def _run_mno_sync_all(job: MnoSyncJob, regions: list[tuple[str, str]]) -> None:
    """Фоновый последовательный обход ВСЕХ регионов справочника одной задачей.

    regions = [(code, name), ...]. Сбой ОДНОГО региона не роняет весь прогон —
    считаем его в regions_failed, пишем в job.error и идём дальше. Итог прогона —
    всегда done (кроме катастрофы вне цикла)."""
    try:
        async with AsyncSessionLocal() as session:
            for code, name in regions:
                job.current_region = name
                try:
                    await _sync_one_region(session, job, int(code))
                    job.regions_done += 1
                except Exception as e:  # noqa: BLE001 — сбой региона не роняет прогон
                    job.regions_failed += 1
                    job.error = f"{name}: {e}"
                    logger.exception(
                        "[mno_sync] all: регион %s (%s) — сбой", code, name
                    )
        job.state = "done"
        job.finished_at = datetime.now(timezone.utc)
        logger.info(
            "[mno_sync] all готов: регионов=%s успешно=%s с ошибками=%s "
            "обнаружено=%s детали=%s записано=%s",
            job.regions_total, job.regions_done, job.regions_failed,
            job.discovered, job.fetched, job.upserted,
        )
    except Exception as e:  # noqa: BLE001 — катастрофа вне цикла (напр. сессия БД)
        job.state = "error"
        job.error = str(e)
        job.finished_at = datetime.now(timezone.utc)
        logger.exception("[mno_sync] all: катастрофа прогона по всем регионам")


def start_mno_sync_all(regions: list[tuple[str, str]]) -> MnoSyncJob:
    """Запускает ФОНОВЫЙ прогон синхронизации МНО по ВСЕМ регионам справочника.

    Если такой прогон уже идёт (по ключу ALL_JOB_KEY, state == running) — возвращает
    его, новый не плодит. regions = [(code, name), ...] в нужном порядке обхода.
    """
    existing = get_region_job(ALL_JOB_KEY)
    if existing is not None and existing.state == "running":
        return existing

    job = MnoSyncJob(
        job_id=str(uuid.uuid4()),
        region_code=ALL_JOB_KEY,
        region_name="Все регионы",
        scope="all",
        regions_total=len(regions),
    )
    _jobs[job.job_id] = job
    _jobs_by_region[ALL_JOB_KEY] = job.job_id

    task = asyncio.create_task(_run_mno_sync_all(job, regions))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return job


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
