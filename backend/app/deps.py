from datetime import datetime, timezone

from fastapi import Depends
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from .database import get_db
from .core.security import decode_token
from .core.errors import AppError, InvalidCredentialsError, UserInactiveError
from .models import User, Volunteer

oauth2_scheme = HTTPBearer()


async def get_current_user(
    token=Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Достаёт текущего пользователя по access-токену (Bearer)."""
    try:
        payload = decode_token(token.credentials)
        user_id = payload.get("sub")
        if user_id is None:
            raise InvalidCredentialsError()

        # Это должен быть именно access-токен, не refresh
        if payload.get("type") != "access":
            raise InvalidCredentialsError()

        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise InvalidCredentialsError()

    except ValueError:
        raise InvalidCredentialsError()

    result = await session.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise InvalidCredentialsError()

    if not user.is_active:
        raise UserInactiveError()

    return user


async def get_current_volunteer(
    token=Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> Volunteer:
    """Текущий волонтёр по логин-токену (typ="volunteer").

    Изоляция: требуем claim typ=="volunteer" → admin access-токен (там "type", не "typ")
    сюда не пройдёт; sub волонтёра ищем в volunteers (не в users). Любой сбой токена и
    отсутствие/блокировка волонтёра → 401 NOT_AUTHENTICATED (не раскрываем причину).
    """
    unauthenticated = AppError(
        code="NOT_AUTHENTICATED",
        message="Требуется авторизация волонтёра",
        status_code=401,
    )
    try:
        payload = decode_token(token.credentials)
    except ValueError:
        raise unauthenticated

    if payload.get("typ") != "volunteer":
        raise unauthenticated

    vol_id = payload.get("sub")
    if vol_id is None:
        raise unauthenticated
    try:
        vol_uuid = UUID(vol_id)
    except (ValueError, TypeError):
        raise unauthenticated

    result = await session.execute(
        select(Volunteer).where(Volunteer.id == vol_uuid)
    )
    volunteer = result.scalar_one_or_none()

    if volunteer is None or not volunteer.is_active:
        raise unauthenticated

    # «Последняя авторизация» = последний запрос волонтёра по его JWT. Пишем с
    # троттлингом (≤1 раз в минуту), чтобы не коммитить на КАЖДЫЙ запрос.
    now = datetime.now(timezone.utc)
    last_seen = volunteer.last_seen_at
    if last_seen is None or (now - last_seen).total_seconds() > 60:
        volunteer.last_seen_at = now
        await session.commit()

    return volunteer
