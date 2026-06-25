"""Аутентификация: проверка пароля с anti-enumeration и DB-lockout (SPEC §3)."""

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    UserInactiveError,
)
from ..core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from ..models import User


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    """Проверка email+пароля с защитой от брутфорса.

    - Anti-enumeration: неизвестный email отдаёт ту же 401 INVALID_CREDENTIALS,
      что и неверный пароль; счётчик при этом не трогаем.
    - DB-lockout: failed_login_attempts / locked_until в БД — надёжно при 2+ воркерах.
      5 неудач → блок на 15 мин (429 ACCOUNT_LOCKED).
    - inactive → 403 USER_INACTIVE.
    - Успех: сброс счётчика; status 'invited' → 'active'.
    Коммитит внутри (auth-сервис коммитит сам).
    """
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # Неизвестный email — сразу 401, счётчик не трогаем (anti-enumeration)
    if user is None:
        raise InvalidCredentialsError()

    now = datetime.now(timezone.utc)

    # Проверка активной блокировки
    if user.locked_until is not None:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)

        if locked_until > now:
            # Аккаунт уже залочен — раскрываем оставшееся время (пользователь о блоке знает)
            remaining = locked_until - now
            minutes_left = math.ceil(remaining.total_seconds() / 60)
            raise AccountLockedError(minutes_left=minutes_left)
        # Окно истекло — сбрасываем и продолжаем проверку
        user.failed_login_attempts = 0
        user.locked_until = None

    # Проверка пароля
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        await session.commit()
        # Не раскрываем факт блокировки — единый ответ
        raise InvalidCredentialsError()

    # Пароль верен
    if not user.is_active:
        # Счётчик у заблокированного не сбрасываем
        raise UserInactiveError()

    # Успешный вход — сброс счётчика
    if user.failed_login_attempts != 0 or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None

    # invited → active при первом успешном входе
    if user.status == "invited":
        user.status = "active"

    await session.commit()
    await session.refresh(user)
    return user


def create_tokens(user_id: str) -> tuple[str, str]:
    """Возвращает (access_token, refresh_token) для sub=user_id."""
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})
    return access_token, refresh_token
