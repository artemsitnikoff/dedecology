"""arq-воркер фоновой синхронизации МНО из ФГИС. Запуск: ``arq app.worker.WorkerSettings``.

Отдельный процесс (сервис ``worker`` в docker-compose), переиспользует образ бэкенда.
Задачи исполняют реальный краул (app.services.mno_worker) и пишут прогресс в Redis —
общий с веб-воркерами. Веб только кладёт задачу в очередь (enqueue), не краулит сам.

max_tries=1: убитую деплоем/крашем задачу НЕ воскрешаем зомби-ретраями (иначе она
держала бы «running» и блокировала кнопку). Повторный запуск дешёвый: уже записанные МНО
пропускаются на уровне батчей по `fgis_id` (детали заново не тянем).

on_startup: при старте воркера осиротевшие задачи (state=running после рестарта)
помечаются 'interrupted', указатели снимаются → кнопка в UI разблокируется мгновенно.
"""

import logging
import sys

from arq.connections import RedisSettings

from .config import settings
from .redis_client import get_redis
from .services import mno_jobs, mno_worker


def _configure_app_logging() -> None:
    """Логи приложения (`app.*`) → stdout воркера на уровне INFO.

    arq на старте настраивает СВОЁ логирование через logging.dictConfig и по умолчанию
    ГЛУШИТ уже существующие сторонние логгеры (disable_existing_loggers) — из-за этого
    наши строки (`[mno_worker] батч …`, `[fgis] обход …`) не выводились вообще, и мы не
    видели, где встаёт синхронизация. Явно вешаем хендлер на пакет 'app' и снимаем
    disabled с уже созданных app.*-логгеров. Вызывается в on_startup (ПОСЛЕ arq-настройки)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    app_logger = logging.getLogger("app")
    app_logger.handlers = [handler]
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    # Снять disabled с дочерних app.*-логгеров, которые arq мог выключить (иначе их
    # записи гасятся до пропагации к 'app' с хендлером).
    for name, lg in logging.root.manager.loggerDict.items():
        if name.startswith("app") and isinstance(lg, logging.Logger):
            lg.disabled = False


async def sync_region_task(ctx, job_id, region_code, region_name):
    """arq-задача: синхронизация МНО одного региона."""
    await mno_worker.run_sync_region(get_redis(), job_id, region_code, region_name)


async def sync_all_task(ctx, job_id, region_pairs):
    """arq-задача: синхронизация МНО по всем регионам справочника (последовательно)."""
    await mno_worker.run_sync_all(get_redis(), job_id, region_pairs)


async def _on_startup(ctx) -> None:
    """При старте воркера: включаем логи приложения + чистим осиротевшие «running»-задачи."""
    _configure_app_logging()
    await mno_jobs.finalize_orphaned_jobs(get_redis())


class WorkerSettings:
    """Настройки arq-воркера (см. `arq app.worker.WorkerSettings`)."""

    functions = [sync_region_task, sync_all_task]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    job_timeout = 60 * 60 * 6  # до 6 часов на полный прогон «все регионы»
    max_tries = 1              # без зомби-ретраев; возобновление — по клику (skip готовых)
    keep_result = 3600
    on_startup = _on_startup
