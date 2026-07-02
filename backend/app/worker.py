"""arq-воркер фоновой синхронизации МНО из ФГИС. Запуск: ``arq app.worker.WorkerSettings``.

Отдельный процесс (сервис ``worker`` в docker-compose), переиспользует образ бэкенда.
Задачи исполняют реальный краул (app.services.mno_worker) и пишут прогресс в Redis —
общий с веб-воркерами. Веб только кладёт задачу в очередь (enqueue), не краулит сам.

max_tries=1: убитую деплоем/крашем задачу НЕ воскрешаем зомби-ретраями (иначе она
держала бы «running» и блокировала кнопку). Возобновление — по клику «Все регионы»:
пройденные регионы пропускаются по постоянным маркерам region_synced (дёшево).

on_startup: при старте воркера осиротевшие задачи (state=running после рестарта)
помечаются 'interrupted', указатели снимаются → кнопка в UI разблокируется мгновенно.
"""

from arq.connections import RedisSettings

from .config import settings
from .redis_client import get_redis
from .services import mno_jobs, mno_worker


async def sync_region_task(ctx, job_id, region_code, region_name):
    """arq-задача: синхронизация МНО одного региона."""
    await mno_worker.run_sync_region(get_redis(), job_id, region_code, region_name)


async def sync_all_task(ctx, job_id, region_pairs):
    """arq-задача: синхронизация МНО по всем регионам справочника (последовательно)."""
    await mno_worker.run_sync_all(get_redis(), job_id, region_pairs)


async def _on_startup(ctx) -> None:
    """При старте воркера чистим осиротевшие «running»-задачи → UI не залипает."""
    await mno_jobs.finalize_orphaned_jobs(get_redis())


class WorkerSettings:
    """Настройки arq-воркера (см. `arq app.worker.WorkerSettings`)."""

    functions = [sync_region_task, sync_all_task]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    job_timeout = 60 * 60 * 6  # до 6 часов на полный прогон «все регионы»
    max_tries = 1              # без зомби-ретраев; возобновление — по клику (skip готовых)
    keep_result = 3600
    on_startup = _on_startup
