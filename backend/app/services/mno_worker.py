"""Реальный краул МНО из ФГИС + запись прогресса в Redis.

Исполняется arq-воркером (app.worker), НЕ в веб-процессе. Переиспользует краулер и
upsert из fgis/mno_sync, но состояние прогресса ведёт в Redis (mno_jobs) — общее для
всех uvicorn-воркеров, переживает рестарты. Прогресс зеркалится в Redis на КАЖДЫЙ батч.

Прогон «все регионы» умеет ВОЗОБНОВЛЯТЬСЯ: пройденные регионы отмечаются в done-set
(mark_region_done), и при ретрае воркера (max_tries) они пропускаются (is_region_done).
"""

import logging

from ..database import AsyncSessionLocal
from . import fgis, mno_sync
from .mno_jobs import (
    initial_progress,
    is_region_done,
    mark_region_done,
    utcnow,
    write_progress,
)

logger = logging.getLogger(__name__)


async def _crawl_region(redis, job_id, prog, session, region_id: int) -> None:
    """Потоковый краул одного региона: фильтр → id батчами → детали → upsert → commit,
    с зеркалированием прогресса в Redis на каждый батч.

    Счётчики prog[discovered|fetched|upserted] — НАКОПИТЕЛЬНЫЕ (годится и для одиночного
    региона, и для суммирования в прогоне «все регионы»). DB-сессию отдаёт вызывающий."""
    filter_id = await fgis.create_filter(region_id)

    base_disc = prog["discovered"]  # накоплено к началу этого региона

    def _prog(discovered: int) -> None:
        prog["discovered"] = base_disc + discovered

    async def _on_batch(batch: list[str]) -> None:
        # Краулер отдал очередные ≤100 НОВЫХ id → детали + upsert + commit + зеркало в Redis.
        objs = await fgis.cluster_details(batch, region_id)
        prog["fetched"] += len(objs)
        prog["upserted"] += await mno_sync._upsert_batch(session, region_id, objs)
        await session.commit()
        await write_progress(redis, job_id, prog)

    _, issues = await fgis.enumerate_region_mno_ids(
        filter_id, region_id, on_progress=_prog, on_batch=_on_batch
    )
    for issue in issues:
        logger.warning("[mno_worker] регион %s: %s", region_id, issue)


async def run_sync_region(redis, job_id, region_code, region_name) -> None:
    """Фоновая синхронизация ОДНОГО региона: своя DB-сессия, прогресс — в Redis."""
    prog = initial_progress(
        job_id, region_code, region_name, scope="region", regions_total=1
    )
    prog["current_region"] = region_name
    await write_progress(redis, job_id, prog)
    try:
        async with AsyncSessionLocal() as session:
            await _crawl_region(redis, job_id, prog, session, int(region_code))
        prog["state"] = "done"
        logger.info(
            "[mno_worker] регион %s готов: обнаружено=%s детали=%s записано=%s",
            region_code, prog["discovered"], prog["fetched"], prog["upserted"],
        )
    except Exception as e:  # noqa: BLE001 — честно фиксируем ошибку в задаче
        prog["state"] = "error"
        prog["error"] = str(e)
        logger.exception("[mno_worker] регион %s: сбой синхронизации", region_code)
    finally:
        prog["finished_at"] = utcnow()
        await write_progress(redis, job_id, prog)


async def run_sync_all(redis, job_id, region_pairs) -> None:
    """Фоновый последовательный прогон по ВСЕМ регионам одной задачей.

    region_pairs = [(code, name), ...]. Сбой ОДНОГО региона не роняет прогон
    (regions_failed++, идём дальше). Пройденные регионы копятся в done-set → при ретрае
    воркера (max_tries) прогон ВОЗОБНОВЛЯЕТСЯ, пропуская уже сделанное."""
    prog = initial_progress(
        job_id, "__all__", "Все регионы", scope="all", regions_total=len(region_pairs)
    )
    await write_progress(redis, job_id, prog)
    try:
        async with AsyncSessionLocal() as session:
            for code, name in region_pairs:
                # RESUME: регион уже пройден в этом прогоне (ретрай воркера) — пропускаем.
                if await is_region_done(redis, job_id, code):
                    prog["regions_done"] += 1
                    await write_progress(redis, job_id, prog)
                    continue
                prog["current_region"] = name
                await write_progress(redis, job_id, prog)
                try:
                    await _crawl_region(redis, job_id, prog, session, int(code))
                    prog["regions_done"] += 1
                    await mark_region_done(redis, job_id, code)
                except Exception as e:  # noqa: BLE001 — сбой региона не роняет прогон
                    prog["regions_failed"] += 1
                    prog["error"] = f"{name}: {e}"
                    logger.exception(
                        "[mno_worker] all: регион %s (%s) — сбой", code, name
                    )
                await write_progress(redis, job_id, prog)
        prog["state"] = "done"
        logger.info(
            "[mno_worker] all готов: регионов=%s успешно=%s с ошибками=%s "
            "обнаружено=%s детали=%s записано=%s",
            prog["regions_total"], prog["regions_done"], prog["regions_failed"],
            prog["discovered"], prog["fetched"], prog["upserted"],
        )
    except Exception as e:  # noqa: BLE001 — катастрофа вне цикла (напр. сессия БД)
        prog["state"] = "error"
        prog["error"] = str(e)
        logger.exception("[mno_worker] all: катастрофа прогона по всем регионам")
    finally:
        prog["finished_at"] = utcnow()
        await write_progress(redis, job_id, prog)
