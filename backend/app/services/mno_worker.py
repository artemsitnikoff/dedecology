"""Реальный краул МНО из ФГИС + запись прогресса в Redis.

Исполняется arq-воркером (app.worker), НЕ в веб-процессе. Переиспользует краулер и
upsert из fgis/mno_sync, но состояние прогресса ведёт в Redis (mno_jobs) — общее для
всех uvicorn-воркеров, переживает рестарты. Прогресс зеркалится в Redis на КАЖДЫЙ батч.

Прогон «все регионы» умеет ВОЗОБНОВЛЯТЬСЯ: пройденные регионы отмечаются в done-set
(mark_region_done), и при ретрае воркера (max_tries) они пропускаются (is_region_done).
"""

import logging

from sqlalchemy import select

from ..database import AsyncSessionLocal
from ..models import Mno
from . import fgis, mno_sync
from .mno_jobs import (
    initial_progress,
    is_cancelled,
    is_region_done,
    is_region_recently_synced,
    mark_region_done,
    mark_region_synced,
    utcnow,
    write_progress,
)

logger = logging.getLogger(__name__)


class _CancelledSync(Exception):
    """Прогон отменён из UI (флаг mno:cancel:{job_id}). Прерывает краул на ближайшем батче."""


async def _existing_fgis_ids(session, ids: list[str]) -> set[str]:
    """Какие из fgis_id уже есть в БД — их детали заново НЕ тянем (дешёвое возобновление).

    Один IN-запрос на батч экономит дорогие сетевые обращения к ФГИС за деталями уже
    записанных МНО: обрыв/деплой/повторный запуск промотываются мимо сделанного."""
    if not ids:
        return set()
    rows = await session.execute(select(Mno.fgis_id).where(Mno.fgis_id.in_(ids)))
    return {row[0] for row in rows.all() if row[0]}


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
        # Отмена из UI: проверяем ДО обработки батча — так прогон обрывается в пределах
        # ~100 обнаруженных id (отзывчиво), не дожидаясь конца региона.
        if await is_cancelled(redis, job_id):
            raise _CancelledSync()
        # Пропускаем уже записанные МНО (fgis_id в БД) — детали тянем ТОЛЬКО для новых.
        # Так возобновление после обрыва/деплоя дёшево: регион промотывается мимо сделанного.
        existing = await _existing_fgis_ids(session, batch)
        prog["skipped"] += len(existing)  # уже были в БД — видимый прогресс на re-скане
        fresh = [mno_id for mno_id in batch if mno_id not in existing]
        if fresh:
            objs = await fgis.cluster_details(fresh, region_id)
            prog["fetched"] += len(objs)
            prog["upserted"] += await mno_sync._upsert_batch(session, region_id, objs)
            await session.commit()
        await write_progress(redis, job_id, prog)

    async def _tick() -> None:
        # Каждый раунд обхода (в т.ч. «пустой хвост», где on_batch молчит): двигаем
        # heartbeat updated_at (не выглядит зависшим) и отзывчиво проверяем отмену.
        if await is_cancelled(redis, job_id):
            raise _CancelledSync()
        await write_progress(redis, job_id, prog)

    _, issues = await fgis.enumerate_region_mno_ids(
        filter_id, region_id, on_progress=_prog, on_batch=_on_batch, on_tick=_tick
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
    except _CancelledSync:  # отмена из UI — не ошибка, честно помечаем «cancelled»
        prog["state"] = "cancelled"
        logger.info("[mno_worker] регион %s: синхронизация отменена из UI", region_code)
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
                # ОТМЕНА из UI (перед регионом): фиксируем и прекращаем прогон.
                if await is_cancelled(redis, job_id):
                    prog["state"] = "cancelled"
                    logger.info("[mno_worker] all: синхронизация отменена из UI")
                    break
                # RESUME: регион уже пройден в этом прогоне (ретрай воркера) — пропускаем.
                if await is_region_done(redis, job_id, code):
                    prog["regions_done"] += 1
                    await write_progress(redis, job_id, prog)
                    continue
                # ПРОПУСК НАСОВСЕМ: регион синхронизирован недавно (маркер ещё жив) — не
                # пере-сканируем готовое (большой первый регион не блокирует остальные).
                if await is_region_recently_synced(redis, code):
                    prog["regions_done"] += 1
                    await write_progress(redis, job_id, prog)
                    continue
                prog["current_region"] = name
                await write_progress(redis, job_id, prog)
                try:
                    await _crawl_region(redis, job_id, prog, session, int(code))
                    prog["regions_done"] += 1
                    await mark_region_done(redis, job_id, code)
                    await mark_region_synced(redis, code)
                except _CancelledSync:  # отмена сработала в пределах региона (на батче)
                    prog["state"] = "cancelled"
                    logger.info("[mno_worker] all: синхронизация отменена из UI")
                    await write_progress(redis, job_id, prog)
                    return
                except Exception as e:  # noqa: BLE001 — сбой региона не роняет прогон
                    prog["regions_failed"] += 1
                    prog["error"] = f"{name}: {e}"
                    logger.exception(
                        "[mno_worker] all: регион %s (%s) — сбой", code, name
                    )
                await write_progress(redis, job_id, prog)
        if prog["state"] != "cancelled":
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
