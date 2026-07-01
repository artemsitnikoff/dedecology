"""Офлайн-фикстуры тестов: ASGI httpx-клиент + переопределённые зависимости.

БД не поднимается (модели на Postgres-типах) — сервисный слой мокается в тестах,
а session/current_user приходят через dependency_overrides. Поэтому:
  - session — AsyncMock (commit/flush/execute — корутины);
  - httpx Response.json()/.status_code — СИНХРОННЫЕ, проверяются напрямую.
"""

import os
from unittest.mock import AsyncMock
from uuid import uuid4

# Обязательные настройки до импорта app (config.Settings требует их)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-please-change")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import get_db  # noqa: E402
from app.deps import get_current_user  # noqa: E402
from app.core.permissions import require_admin, require_superadmin  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture
def fake_session() -> AsyncMock:
    """Поддельная AsyncSession: awaitable-методы как корутины."""
    session = AsyncMock()
    return session


@pytest.fixture
def current_user() -> User:
    """Активный админ — действующее лицо запросов."""
    user = User(
        email="admin@dedekolog.ru",
        password_hash="x",
        fio="Дед Эколог",
        role="admin",
        status="active",
        is_active=True,
        is_superadmin=False,
    )
    user.id = uuid4()
    return user


@pytest_asyncio.fixture
async def client(fake_session, current_user):
    """httpx-клиент к приложению с переопределёнными зависимостями."""
    async def _get_db_override():
        yield fake_session

    async def _current_user_override():
        return current_user

    async def _require_admin_override():
        return None

    async def _require_superadmin_override():
        return None

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = _current_user_override
    app.dependency_overrides[require_admin] = _require_admin_override
    app.dependency_overrides[require_superadmin] = _require_superadmin_override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
