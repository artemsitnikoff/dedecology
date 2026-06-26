"""Тесты /users и /profile — офлайн, сервисный слой замокан."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.errors import ConflictError, ForbiddenError
from app.core.security import get_password_hash, verify_password
from app.models import User
from app.schemas.user import UserCreate, UserListItem
from app.services.user import create_user, delete_user, set_user_password


def _user(role="user", status="active", is_superadmin=False):
    u = User(
        email="op@dedekolog.ru",
        password_hash="x",
        fio="Иванова Светлана Петровна",
        role=role,
        status=status,
        is_active=True,
        is_superadmin=is_superadmin,
    )
    u.id = uuid4()
    return u


@pytest.mark.asyncio
async def test_list_users(client):
    items = [
        UserListItem(
            id=uuid4(), fio="Иванова Светлана", email="op@dedekolog.ru",
            role="user", status="active", is_superadmin=False,
        ),
        UserListItem(
            id=uuid4(), fio="Дед Эколог", email="pulse@reo.ru",
            role="admin", status="active", is_superadmin=True,
        ),
    ]
    with patch("app.api.v1.users.list_users", new=AsyncMock(return_value=items)):
        resp = await client.get("/api/v1/users")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["email"] == "op@dedekolog.ru"
    # is_superadmin отдаётся в списке пользователей
    assert body[0]["is_superadmin"] is False
    assert body[1]["is_superadmin"] is True


@pytest.mark.asyncio
async def test_create_user_active_no_temp_password(client):
    user = _user(status="active")
    with patch(
        "app.api.v1.users.create_user",
        new=AsyncMock(return_value=user),
    ):
        resp = await client.post(
            "/api/v1/users",
            json={
                "fio": "Иванова Светлана Петровна",
                "email": "op@dedekolog.ru",
                "role": "user",
                "password": "secret123",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    # инвайт-флоу убран: пользователь сразу active, без temp_password
    assert body["status"] == "active"
    assert body["email"] == "op@dedekolog.ru"
    assert body["is_superadmin"] is False
    assert "temp_password" not in body


@pytest.mark.asyncio
async def test_create_user_requires_password_422(client):
    # пароль обязателен и не короче 6 символов
    resp = await client.post(
        "/api/v1/users",
        json={"fio": "X", "email": "x@dedekolog.ru", "role": "user", "password": "abc"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_user_duplicate_email_409(client):
    with patch(
        "app.api.v1.users.create_user",
        new=AsyncMock(side_effect=ConflictError("Пользователь с таким email уже существует")),
    ):
        resp = await client.post(
            "/api/v1/users",
            json={
                "fio": "X", "email": "dup@dedekolog.ru", "role": "user",
                "password": "secret123",
            },
        )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_set_user_password_204(client):
    with patch("app.api.v1.users.set_user_password", new=AsyncMock(return_value=None)):
        resp = await client.post(
            f"/api/v1/users/{uuid4()}/password",
            json={"new_password": "newsecret"},
        )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_set_user_password_too_short_422(client):
    resp = await client.post(
        f"/api/v1/users/{uuid4()}/password",
        json={"new_password": "abc"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_set_password_superadmin_forbidden(client):
    with patch(
        "app.api.v1.users.set_user_password",
        new=AsyncMock(side_effect=ForbiddenError("Нельзя сбросить пароль супер-админа")),
    ):
        resp = await client.post(
            f"/api/v1/users/{uuid4()}/password",
            json={"new_password": "newsecret"},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_user_success_204(client):
    with patch("app.api.v1.users.delete_user", new=AsyncMock(return_value=None)):
        resp = await client.delete(f"/api/v1/users/{uuid4()}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_superadmin_forbidden(client):
    with patch(
        "app.api.v1.users.delete_user",
        new=AsyncMock(side_effect=ForbiddenError("Нельзя удалить супер-админа")),
    ):
        resp = await client.delete(f"/api/v1/users/{uuid4()}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_admin_forbidden(client):
    with patch(
        "app.api.v1.users.delete_user",
        new=AsyncMock(side_effect=ForbiddenError("Нельзя удалить администратора")),
    ):
        resp = await client.delete(f"/api/v1/users/{uuid4()}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_self_forbidden(client):
    with patch(
        "app.api.v1.users.delete_user",
        new=AsyncMock(side_effect=ForbiddenError("Нельзя удалить самого себя")),
    ):
        resp = await client.delete(f"/api/v1/users/{uuid4()}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_profile(client, current_user):
    updated = _user()
    updated.fio = "Новое Имя"
    with patch("app.api.v1.profile.update_profile", new=AsyncMock(return_value=updated)):
        resp = await client.patch("/api/v1/profile", json={"fio": "Новое Имя"})
    assert resp.status_code == 200
    assert resp.json()["fio"] == "Новое Имя"


@pytest.mark.asyncio
async def test_change_password(client):
    with patch("app.api.v1.profile.reset_own_password", new=AsyncMock(return_value=None)):
        resp = await client.post(
            "/api/v1/profile/password", json={"new_password": "newsecret"}
        )
    assert resp.status_code == 200
    assert "message" in resp.json()


@pytest.mark.asyncio
async def test_change_password_too_short_422(client):
    resp = await client.post("/api/v1/profile/password", json={"new_password": "abc"})
    assert resp.status_code == 422


# --- Сервисный слой: реальная логика (без живой БД, session подменён) ---

def _no_existing_session() -> MagicMock:
    """Фейк-сессия: execute().scalar_one_or_none()==None; add синхронный, flush — корутина."""
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_service_create_user_active_with_working_password():
    """create_user: status='active', is_superadmin=False, заданный пароль валиден."""
    session = _no_existing_session()
    data = UserCreate(
        fio="Иванова Светлана Петровна",
        email="op@dedekolog.ru",
        role="user",
        password="secret123",
    )
    user = await create_user(session, data, actor_user_id=uuid4())
    assert user.status == "active"
    assert user.is_superadmin is False
    # пароль реально хешируется и проверяется
    assert verify_password("secret123", user.password_hash) is True
    assert verify_password("wrong-password", user.password_hash) is False


@pytest.mark.asyncio
async def test_service_set_password_changes_hash():
    """set_user_password: старый пароль перестаёт работать, новый — работает."""
    target = _user(status="active")
    target.password_hash = get_password_hash("old-password")
    session = MagicMock()
    session.flush = AsyncMock()
    with patch("app.services.user.get_user", new=AsyncMock(return_value=target)):
        await set_user_password(session, target.id, "new-password", actor_user_id=uuid4())
    assert verify_password("new-password", target.password_hash) is True
    assert verify_password("old-password", target.password_hash) is False


@pytest.mark.asyncio
async def test_service_set_password_superadmin_forbidden():
    """set_user_password супер-админу → ForbiddenError (пароль не меняется)."""
    target = _user(role="admin", status="active", is_superadmin=True)
    target.password_hash = get_password_hash("kept-password")
    session = AsyncMock()
    with patch("app.services.user.get_user", new=AsyncMock(return_value=target)):
        with pytest.raises(ForbiddenError):
            await set_user_password(session, target.id, "hacked", actor_user_id=uuid4())
    # пароль остался прежним
    assert verify_password("kept-password", target.password_hash) is True


@pytest.mark.asyncio
async def test_service_delete_superadmin_forbidden():
    """delete_user супер-админа → ForbiddenError."""
    target = _user(role="admin", status="active", is_superadmin=True)
    session = AsyncMock()
    with patch("app.services.user.get_user", new=AsyncMock(return_value=target)):
        with pytest.raises(ForbiddenError):
            await delete_user(session, target.id, actor_user_id=uuid4())
