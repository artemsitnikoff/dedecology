"""Тесты пула цитат — офлайн (моки сессии): выборка из БД, фолбэк, сид, размер пула."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import quotes as quotes_service
from app.services.quotes_data import QUOTES, QUOTES_CURATED, QUOTES_EXTRA


class _ACtx:
    """Мини async-context-manager, отдающий заранее заданную сессию."""

    def __init__(self, session):
        self._s = session

    async def __aenter__(self):
        return self._s

    async def __aexit__(self, *exc):
        return False


def test_quotes_pool_large_and_unique():
    """Пул ≥300 строк, все уникальны; курируемые — реальные (ёлочки), extra — без приписывания."""
    assert len(QUOTES) >= 300
    assert len(set(QUOTES)) == len(QUOTES)
    assert QUOTES == QUOTES_CURATED + QUOTES_EXTRA
    # extra — оригинальные, БЕЗ кавычек-ёлочек (не выдаём за чужие цитаты).
    assert all("«" not in q and "»" not in q for q in QUOTES_EXTRA)


@pytest.mark.asyncio
async def test_nature_quote_from_db():
    """Непустая таблица → возвращается строка из БД (ORDER BY random)."""
    res = MagicMock()
    res.scalar_one_or_none.return_value = "тест-цитата из БД"
    session = AsyncMock()
    session.execute = AsyncMock(return_value=res)
    with patch("app.services.quotes.AsyncSessionLocal", return_value=_ACtx(session)):
        q = await quotes_service.nature_quote()
    assert q == "тест-цитата из БД"


@pytest.mark.asyncio
async def test_nature_quote_empty_table_falls_back_to_pool():
    """Пустая таблица (None) → фолбэк на код-список QUOTES."""
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=res)
    with patch("app.services.quotes.AsyncSessionLocal", return_value=_ACtx(session)):
        q = await quotes_service.nature_quote()
    assert q in QUOTES


@pytest.mark.asyncio
async def test_nature_quote_db_error_falls_back():
    """Сбой БД → не бросает, отдаёт цитату из код-списка."""
    with patch(
        "app.services.quotes.AsyncSessionLocal", side_effect=RuntimeError("no db")
    ):
        q = await quotes_service.nature_quote()
    assert q in QUOTES


@pytest.mark.asyncio
async def test_seed_quotes_inserts_when_empty():
    """seed_quotes: пустая таблица → вставляет весь пул."""
    count_res = MagicMock()
    count_res.scalar_one.return_value = 0
    session = AsyncMock()
    session.execute = AsyncMock(return_value=count_res)
    added: list = []
    session.add_all = MagicMock(side_effect=added.extend)
    n = await quotes_service.seed_quotes(session)
    assert n == len(QUOTES)
    assert len(added) == len(QUOTES)


@pytest.mark.asyncio
async def test_seed_quotes_skips_when_populated():
    """seed_quotes: таблица не пуста → ничего не вставляет (идемпотентно)."""
    count_res = MagicMock()
    count_res.scalar_one.return_value = 42
    session = AsyncMock()
    session.execute = AsyncMock(return_value=count_res)
    session.add_all = MagicMock()
    n = await quotes_service.seed_quotes(session)
    assert n == 0
    session.add_all.assert_not_called()
