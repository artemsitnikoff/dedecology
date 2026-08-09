"""Entrypoint долгоживущего Telegram long-polling воркера ЭкоПульс.

Outbound-only: соединяется наружу с Telegram Bot API, тянет апдейты (getUpdates,
long-poll) и пересылает каждое обращение в backend intake API. Входящего порта /
вебхука нет.

Только polling: групповой notify-loop (как в maxbot) сознательно НЕ подключён —
бот отвечает прямо в чате, где пришло сообщение.
"""

from __future__ import annotations

import asyncio
import logging

from .bot import dispatch
from .config import settings
from .tgapi import DEFAULT_POLL_TIMEOUT, TelegramAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dedecology.telegrambot")


class _TokenRedactingFilter(logging.Filter):
    """Маскирует токен бота в ТЕКСТЕ лог-записи (record.getMessage) — defense-in-depth.

    Вешается на КОРНЕВЫЕ ХЕНДЛЕРЫ (см. main): фильтр хендлера применяется ко ВСЕМ записям,
    включая сторонние логгеры — httpx кладёт URL с токеном (…/bot<token>/…) в текст. Правит
    только message (record.msg/args), но НЕ трейсбек `logger.exception` (record.exc_text
    форматируется отдельно) — утечка через трейсбек закрыта В ИСТОЧНИКЕ (get_updates
    санитизирует raise_for_status `from None`). Основной барьер для httpx-логов запросов —
    setLevel(WARNING) в main (глушит per-request INFO-строки целиком)."""

    def __init__(self, secret: str) -> None:
        super().__init__()
        self._secret = secret

    def filter(self, record: logging.LogRecord) -> bool:
        if self._secret:
            try:
                msg = record.getMessage()
            except Exception:  # noqa: BLE001 — форматирование не должно ронять лог
                return True
            if self._secret in msg:
                record.msg = msg.replace(self._secret, "<TOKEN>")
                record.args = ()
        return True


# Пауза перед повтором, если getUpdates упал (сеть/5xx/таймаут) — не долбим API впустую.
_ERROR_BACKOFF = 3.0


async def _poll_loop(api: TelegramAPI) -> None:
    """Бесконечный long-poll: getUpdates(offset) → апдейты обрабатываются ПОСЛЕДОВАТЕЛЬНО.

    offset двигаем на max(update_id)+1 СРАЗУ после получения пачки (апдейты не
    перечитываются повторно). dispatch КАЖДОГО апдейта — await по очереди (как
    последовательный поллер maxapi у maxbot): это исключает гонки между апдейтами одной
    пачки (двойная отправка / быстрый повтор → один общий PendingReport). Тяжёлое
    (скачивание фото, финализация) обработчики сами уводят в фон через _spawn, чтобы не
    блокировать поллер. Сбой getUpdates → backoff."""
    offset = 0
    while True:
        try:
            updates = await api.get_updates(offset, timeout=DEFAULT_POLL_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — цикл поллинга не умирает никогда
            logger.exception("getUpdates failed — retry after %.1fs", _ERROR_BACKOFF)
            await asyncio.sleep(_ERROR_BACKOFF)
            continue

        for update in updates:
            uid = update.get("update_id") if isinstance(update, dict) else None
            if isinstance(uid, int):
                offset = max(offset, uid + 1)
            # ПОСЛЕДОВАТЕЛЬНО: dispatch сам гасит свои исключения (внутренний try/except),
            # а тяжёлую работу уводит в фон (_spawn) — поллер отзывчив, но апдейты НЕ
            # обрабатываются конкурентно (иначе гонки за общий PendingReport).
            await dispatch(api, update)


async def main() -> None:
    token = settings.TELEGRAM_BOT_TOKEN.get_secret_value()
    # httpx на уровне INFO логирует КАЖДЫЙ запрос строкой "HTTP Request: POST
    # https://api.telegram.org/bot<TOKEN>/..." → полный токен утёк бы в логи. Глушим до WARNING.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # Страховка: маскируем токен в тексте ЛЮБОЙ лог-записи. Фильтр вешаем на КОРНЕВЫЕ ХЕНДЛЕРЫ
    # (не на наш логгер): фильтр хендлера применяется ко ВСЕМ записям, включая сторонние логгеры;
    # записи дочерних логгеров через фильтры родительского логгера НЕ проходят — только хендлера.
    _redactor = _TokenRedactingFilter(token)
    for _h in logging.getLogger().handlers:
        _h.addFilter(_redactor)
    api = TelegramAPI(token)

    # Любой ранее установленный вебхук отбирает апдейты у long-polling (getUpdates 409). Снимаем.
    try:
        await api.delete_webhook(drop_pending_updates=False)
    except Exception as exc:  # noqa: BLE001 — не фатально; логируем и продолжаем
        logger.warning("delete_webhook failed: %s", exc)

    logger.info("Telegram bot polling started — build 0.1.0 (geo + mno + incident-type)")
    try:
        await _poll_loop(api)
    except asyncio.CancelledError:
        logger.info("polling cancelled — shutting down")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("interrupted by user — exiting")
