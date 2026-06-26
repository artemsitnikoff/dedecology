"""Тесты /auth — офлайн, сервисный слой замокан."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.errors import AccountLockedError, InvalidCredentialsError
from app.models import User


def _user(role="user", status="active"):
    u = User(
        email="user@dedekolog.ru",
        password_hash="x",
        fio="Тест Тестов",
        role=role,
        status=status,
        is_active=True,
    )
    u.id = uuid4()
    return u


@pytest.mark.asyncio
async def test_login_success_sets_refresh_cookie(client):
    user = _user()
    with patch("app.api.v1.auth.authenticate_user", new=AsyncMock(return_value=user)), patch(
        "app.api.v1.auth.create_tokens", return_value=("access-tok", "refresh-tok")
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "user@dedekolog.ru", "password": "secret123"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] == "access-tok"
    assert body["token_type"] == "bearer"
    set_cookie = resp.headers.get("set-cookie", "")
    assert "refresh_token=refresh-tok" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth/refresh" in set_cookie


@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_401(client):
    with patch(
        "app.api.v1.auth.authenticate_user",
        new=AsyncMock(side_effect=InvalidCredentialsError()),
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@dedekolog.ru", "password": "wrong"},
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_account_locked_returns_429(client):
    with patch(
        "app.api.v1.auth.authenticate_user",
        new=AsyncMock(side_effect=AccountLockedError(minutes_left=15)),
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "user@dedekolog.ru", "password": "wrong"},
        )
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "ACCOUNT_LOCKED"


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client):
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_logout_deletes_cookie(client):
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert "message" in resp.json()
    assert "refresh_token=" in resp.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_me_returns_current_user(client, current_user):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == current_user.email
    assert body["role"] == "admin"
    assert body["status"] == "active"
    assert body["is_superadmin"] is False
