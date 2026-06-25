"""Тесты /users и /profile — офлайн, сервисный слой замокан."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.errors import ConflictError, ForbiddenError
from app.models import User
from app.schemas.user import UserListItem


def _user(role="user", status="active"):
    u = User(
        email="op@dedekolog.ru",
        password_hash="x",
        fio="Иванова Светлана Петровна",
        role=role,
        status=status,
        is_active=True,
    )
    u.id = uuid4()
    return u


@pytest.mark.asyncio
async def test_list_users(client):
    items = [
        UserListItem(
            id=uuid4(), fio="Иванова Светлана", email="op@dedekolog.ru",
            role="user", status="active",
        )
    ]
    with patch("app.api.v1.users.list_users", new=AsyncMock(return_value=items)):
        resp = await client.get("/api/v1/users")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["email"] == "op@dedekolog.ru"


@pytest.mark.asyncio
async def test_invite_user_returns_temp_password(client):
    user = _user(status="invited")
    with patch(
        "app.api.v1.users.create_invite",
        new=AsyncMock(return_value=(user, "Tmp-Pass-12chars")),
    ):
        resp = await client.post(
            "/api/v1/users",
            json={"fio": "Иванова Светлана Петровна", "email": "op@dedekolog.ru", "role": "user"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["temp_password"] == "Tmp-Pass-12chars"
    assert body["status"] == "invited"
    assert body["email"] == "op@dedekolog.ru"


@pytest.mark.asyncio
async def test_invite_user_duplicate_email_409(client):
    with patch(
        "app.api.v1.users.create_invite",
        new=AsyncMock(side_effect=ConflictError("Пользователь с таким email уже существует")),
    ):
        resp = await client.post(
            "/api/v1/users",
            json={"fio": "X", "email": "dup@dedekolog.ru", "role": "user"},
        )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_delete_user_success_204(client):
    with patch("app.api.v1.users.delete_user", new=AsyncMock(return_value=None)):
        resp = await client.delete(f"/api/v1/users/{uuid4()}")
    assert resp.status_code == 204


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
