"""Авторизация УТКО-совместимого API — OAuth2 password grant (POST /connect/token).

Схема идентична OAuth 2.0: клиент шлёт x-www-form-urlencoded с grant_type=password +
username/password/client_id/client_secret. Сверяем с конфигом (UTKO_*). Успех → наш
JWT (HS256, claim typ="utko", exp=TTL) + НАСТОЯЩИЙ refresh_token (JWT typ=utko_refresh,
долгий exp) — его можно обменять на новую пару через grant_type=refresh_token (stateless,
валидируется подписью/typ, хранилища не требует). Пока UTKO_* не сконфигурированы
(хотя бы один пуст) — токен НЕ выдаём (честный 400).

Защищённые эндпоинты зависят от `require_utko_auth`: валидный Bearer-JWT с typ=utko →
пропуск; иначе 401 Unauthorized (в формате УТКО).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Form, Request
from jose import jwt
from jose.exceptions import JWTError

from ..config import settings
from . import errors
from .schemas import TokenResponse

router = APIRouter()

_ALGO = "HS256"
_TOKEN_TYP = "utko"
_REFRESH_TYP = "utko_refresh"
# refresh-токен живёт дольше access (30 суток) — stateless JWT, валидируется подписью/typ,
# хранилища не требует. grant_type=refresh_token обменивает его на новую пару.
_REFRESH_TTL_SECONDS = 30 * 24 * 3600


def _token_secret() -> str:
    """Секрет подписи УТКО-токена: UTKO_TOKEN_SECRET, иначе общий JWT_SECRET."""
    return settings.UTKO_TOKEN_SECRET or settings.JWT_SECRET


def _utko_configured() -> bool:
    """Все четыре креда заданы → интеграция сконфигурирована и токен можно выдавать."""
    return all(
        bool(v)
        for v in (
            settings.UTKO_CLIENT_ID,
            settings.UTKO_CLIENT_SECRET,
            settings.UTKO_USERNAME,
            settings.UTKO_PASSWORD,
        )
    )


def _creds_valid(username: str, password: str, client_id: str, client_secret: str) -> bool:
    """Сверка кред в постоянном времени (secrets.compare_digest, без раннего выхода)."""
    ok = True
    ok &= secrets.compare_digest(username or "", settings.UTKO_USERNAME or "")
    ok &= secrets.compare_digest(password or "", settings.UTKO_PASSWORD or "")
    ok &= secrets.compare_digest(client_id or "", settings.UTKO_CLIENT_ID or "")
    ok &= secrets.compare_digest(client_secret or "", settings.UTKO_CLIENT_SECRET or "")
    return ok


def issue_access_token(ttl_seconds: int | None = None) -> str:
    """Выдать УТКО access-токен (JWT HS256, claim typ=utko, exp=TTL)."""
    ttl = ttl_seconds if ttl_seconds is not None else settings.UTKO_TOKEN_TTL_SECONDS
    now = datetime.now(timezone.utc)
    payload = {
        "typ": _TOKEN_TYP,
        "sub": settings.UTKO_USERNAME or "utko-client",
        "client_id": settings.UTKO_CLIENT_ID or "",
        "scope": "email offline_access openid profile",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=ttl),
    }
    return jwt.encode(payload, _token_secret(), algorithm=_ALGO)


def decode_access_token(token: str) -> dict | None:
    """Декодировать+проверить УТКО-токен. None на любую ошибку (битый/просрочен/чужой typ)."""
    try:
        payload = jwt.decode(token, _token_secret(), algorithms=[_ALGO])
    except JWTError:
        return None
    if payload.get("typ") != _TOKEN_TYP:
        return None
    return payload


def issue_refresh_token() -> str:
    """Выдать УТКО refresh-токен (JWT HS256, typ=utko_refresh, долгий exp)."""
    now = datetime.now(timezone.utc)
    payload = {
        "typ": _REFRESH_TYP,
        "sub": settings.UTKO_USERNAME or "utko-client",
        "client_id": settings.UTKO_CLIENT_ID or "",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=_REFRESH_TTL_SECONDS),
    }
    return jwt.encode(payload, _token_secret(), algorithm=_ALGO)


def decode_refresh_token(token: str) -> dict | None:
    """Декодировать+проверить refresh-токен. None на ошибку/чужой typ/просрочку."""
    try:
        payload = jwt.decode(token, _token_secret(), algorithms=[_ALGO])
    except JWTError:
        return None
    if payload.get("typ") != _REFRESH_TYP:
        return None
    return payload


async def require_utko_auth(request: Request) -> dict:
    """Зависимость защищённых УТКО-эндпоинтов: валидный Bearer-JWT (typ=utko) → payload.

    Нет заголовка / не Bearer / битый / просроченный / чужой typ → 401 Unauthorized.

    TODO-scope: проверка «наличия прав у пользователя» (строка 0 таблиц проверок, 403
    «Доступ запрещен») — пока ЗАГЛУШКА «всё разрешено»: любой валидный токен проходит.
    Реальная область видимости (регионы/МНО по scope) появится вместе со справочниками.
    """
    authz = request.headers.get("Authorization") or request.headers.get("authorization") or ""
    if not authz.startswith("Bearer "):
        raise errors.unauthorized()
    token = authz[len("Bearer "):].strip()
    payload = decode_access_token(token)
    if payload is None:
        raise errors.unauthorized()
    return payload


@router.post("/connect/token", tags=["УТКО-совместимое API"])
async def connect_token(
    grant_type: str = Form(...),
    username: str = Form(default=""),
    password: str = Form(default=""),
    client_id: str = Form(default=""),
    client_secret: str = Form(default=""),
    refresh_token: str = Form(default=""),
):
    """OAuth2. Content-Type: application/x-www-form-urlencoded.

    Поддержаны два grant_type:
      • password       — username/password/client_id/client_secret (сверка с UTKO_*);
      • refresh_token  — обмен выданного ранее refresh-токена на новую пару.
    grant_type вне набора / неверные креды / битый refresh / не сконфигурировано → 400.
    """
    # Не сконфигурировано — честно не выдаём токен (без реальных кред интеграции нет).
    if not _utko_configured():
        raise errors.bad_request(
            "Client error: `POST /connect/token` resulted in a `400 Bad Request` "
            'response:\n{"error":"invalid_grant","error_description":'
            '"integration_not_configured"}\n'
        )
    if grant_type == "password":
        if not _creds_valid(username, password, client_id, client_secret):
            raise errors.bad_request(
                "Client error: `POST /connect/token` resulted in a `400 Bad Request` "
                'response:\n{"error":"invalid_grant",'
                '"error_description":"invalid_username_or_password"}\n'
            )
    elif grant_type == "refresh_token":
        if not refresh_token or decode_refresh_token(refresh_token) is None:
            raise errors.bad_request(
                "Client error: `POST /connect/token` resulted in a `400 Bad Request` "
                'response:\n{"error":"invalid_grant",'
                '"error_description":"invalid_refresh_token"}\n'
            )
    else:
        raise errors.bad_request(
            "Client error: `POST /connect/token` resulted in a `400 Bad Request` "
            'response:\n{"error":"unsupported_grant_type",'
            '"error_description":"grant_type must be password or refresh_token"}\n'
        )

    ttl = settings.UTKO_TOKEN_TTL_SECONDS
    body = TokenResponse(
        access_token=issue_access_token(ttl),
        expires_in=ttl,
        token_type="Bearer",
        refresh_token=issue_refresh_token(),
    )
    return body.model_dump()
