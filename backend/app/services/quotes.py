"""Мотивирующая эко-строка для показа после успешного приёма обращения.

Берётся СЛУЧАЙНО из таблицы quotes (пул засеян миграцией 0022 из services/quotes_data.py:
курируемые подлинные цитаты + оригинальные эко-строки). Медленный claude CLI (~15-20с на
запрос — замер с прода) для цитат БОЛЬШЕ НЕ используется. nature_quote ВСЕГДА возвращает
непустую строку и не бросает: при недоступности БД / пустой таблице — фолбэк на код-список.
"""

import logging
import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal
from ..models import Quote
from .quotes_data import QUOTES

logger = logging.getLogger(__name__)


async def seed_quotes(session: AsyncSession) -> int:
    """Идемпотентно засевает пул в таблицу quotes, если она пуста.

    Прод сидируется миграцией 0022; это — для локали / первого `python -m app.seed`.
    Возвращает число вставленных строк (0, если уже заполнено). flush, без commit."""
    existing = (await session.execute(select(func.count(Quote.id)))).scalar_one()
    if existing:
        return 0
    session.add_all([Quote(text=q) for q in QUOTES])
    await session.flush()
    return len(QUOTES)


async def nature_quote() -> str:
    """Случайная эко-строка из БД (ORDER BY random()). Пусто/сбой БД → фолбэк на код-список."""
    try:
        async with AsyncSessionLocal() as session:
            text = (
                await session.execute(
                    select(Quote.text).order_by(func.random()).limit(1)
                )
            ).scalar_one_or_none()
        if text:
            return text
    except Exception:  # noqa: BLE001 — БД недоступна → фолбэк, цитата необязательна
        logger.exception("[quotes] выборка из БД не удалась — фолбэк на код-список")
    return random.choice(QUOTES)
