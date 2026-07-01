"""Ленивый синглтон async-Redis клиента для ЧТЕНИЯ/ЗАПИСИ прогресса синхронизации МНО.

Отдельно от arq-пула (тот живёт в ``app.state.arq_pool`` и служит ТОЛЬКО для enqueue
задач). Здесь — клиент общего назначения, которым сервис/эндпоинты пишут и читают
снимок прогресса задач. ``decode_responses=True`` → hgetall/get отдают ``str``, а не
``bytes`` (см. mno_jobs — восстановление типов из строк).

Импорт пакета ``redis`` — ЛЕНИВЫЙ (внутри get_redis): этот модуль импортируется и в
вебе, и в офлайн-тестах, где пакет redis может быть не установлен. Тесты передают в
mno_jobs/mno_worker свой FakeRedis напрямую или мокают ``get_redis`` — реальный клиент
не создаётся. Так веб-приложение и тесты стартуют без установленного redis.
"""

from .config import settings

_client = None


def get_redis():
    """Ленивый синглтон redis.asyncio-клиента (decode_responses=True).

    Клиент redis.asyncio подключается к серверу лениво, на первой команде, поэтому сам
    вызов get_redis() не падает при недоступном Redis — ошибка всплывёт уже на конкретной
    операции (эндпоинт превратит её в ошибку/503).
    """
    global _client
    if _client is None:
        import redis.asyncio as aioredis  # ленивый импорт: см. docstring модуля

        _client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client
