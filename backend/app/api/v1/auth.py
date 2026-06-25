"""Эндпоинты аутентификации (SPEC §3 /auth)."""

from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...core.errors import InvalidCredentialsError
from ...core.security import decode_token
from ...database import get_db
from ...deps import get_current_user
from ...models import User
from ...schemas.auth import LoginRequest, TokenResponse, UserMe
from ...schemas.base import MessageResult
from ...services.auth import authenticate_user, create_tokens

router = APIRouter()

_REFRESH_COOKIE_PATH = "/api/v1/auth/refresh"
_REFRESH_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        path=_REFRESH_COOKIE_PATH,
        max_age=_REFRESH_MAX_AGE,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    """Вход по email+паролю. Access — в теле, refresh — в HttpOnly-cookie."""
    user = await authenticate_user(session, login_data.email, login_data.password)
    access_token, refresh_token = create_tokens(str(user.id))
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    session: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(None),
):
    """Обновление access-токена по refresh-cookie."""
    if refresh_token is None:
        raise InvalidCredentialsError()

    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise InvalidCredentialsError()

    if payload.get("type") != "refresh":
        raise InvalidCredentialsError()

    user_id = payload.get("sub")
    if user_id is None:
        raise InvalidCredentialsError()
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise InvalidCredentialsError()

    result = await session.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise InvalidCredentialsError()

    access_token, new_refresh_token = create_tokens(user_id)
    _set_refresh_cookie(response, new_refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResult)
async def logout(response: Response):
    """Выход — удаляем refresh-cookie."""
    response.delete_cookie(key="refresh_token", path=_REFRESH_COOKIE_PATH)
    return MessageResult(message="Вы вышли из системы")


@router.get("/me", response_model=UserMe)
async def me(current_user: User = Depends(get_current_user)):
    """Текущий пользователь."""
    return UserMe.model_validate(current_user)
