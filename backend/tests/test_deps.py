"""Юнит-тесты зависимостей авторизации — офлайн (session/токены замоканы).

Фокус: get_optional_volunteer — ОПЦИОНАЛЬНАЯ авторизация волонтёра для публичных
POST /intake/form|/mno. Возвращает Volunteer только при валидном активном
volunteer-токене; во всех прочих случаях → None и НИКОГДА не бросает. Плюс: не пишет
last_seen_at и не коммитит (только чтение — иначе преждевременный commit в публичном POST).
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.security import create_access_token, create_volunteer_access_token
from app.deps import get_optional_volunteer
from app.models import Volunteer


def _volunteer(is_active=True):
    v = Volunteer(email="vol@example.com", password_hash="x", is_active=is_active)
    v.id = uuid4()
    v.last_seen_at = None
    return v


def _session_returning(volunteer) -> MagicMock:
    """Фейк-сессия: execute().scalar_one_or_none() → данный волонтёр (или None)."""
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = volunteer
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_optional_volunteer_no_header_returns_none():
    """Нет заголовка Authorization → token=None → None (БД не трогаем)."""
    session = MagicMock()
    session.execute = AsyncMock(side_effect=AssertionError("БД не должна вызываться"))

    assert await get_optional_volunteer(token=None, session=session) is None
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_optional_volunteer_admin_token_returns_none():
    """Admin access-токен (type='access', без typ) → None (не волонтёрский токен)."""
    session = MagicMock()
    session.execute = AsyncMock(side_effect=AssertionError("БД не должна вызываться"))
    admin_tok = create_access_token(data={"sub": str(uuid4())})

    result = await get_optional_volunteer(
        token=SimpleNamespace(credentials=admin_tok), session=session
    )
    assert result is None
    # typ!='volunteer' отсекается ДО запроса к БД.
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_optional_volunteer_valid_active_returns_volunteer():
    """Валидный volunteer-токен + активный волонтёр → сам Volunteer; last_seen НЕ пишется,
    commit НЕ вызывается (только чтение)."""
    vol = _volunteer(is_active=True)
    session = _session_returning(vol)
    tok = create_volunteer_access_token(str(vol.id))

    result = await get_optional_volunteer(
        token=SimpleNamespace(credentials=tok), session=session
    )
    assert result is vol
    assert vol.last_seen_at is None  # запись «последней авторизации» НЕ ведётся
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_optional_volunteer_blocked_returns_none():
    """Заблокированный волонтёр (is_active=False) → None."""
    vol = _volunteer(is_active=False)
    session = _session_returning(vol)
    tok = create_volunteer_access_token(str(vol.id))

    result = await get_optional_volunteer(
        token=SimpleNamespace(credentials=tok), session=session
    )
    assert result is None


@pytest.mark.asyncio
async def test_optional_volunteer_unknown_returns_none():
    """Волонтёр с таким id не найден (scalar_one_or_none → None) → None."""
    session = _session_returning(None)
    tok = create_volunteer_access_token(str(uuid4()))

    result = await get_optional_volunteer(
        token=SimpleNamespace(credentials=tok), session=session
    )
    assert result is None


@pytest.mark.asyncio
async def test_optional_volunteer_garbage_token_returns_none():
    """Битый (не декодируемый) токен → None, без обращения к БД и без исключения."""
    session = MagicMock()
    session.execute = AsyncMock(side_effect=AssertionError("БД не должна вызываться"))

    result = await get_optional_volunteer(
        token=SimpleNamespace(credentials="garbage.token.value"), session=session
    )
    assert result is None
    session.execute.assert_not_called()
