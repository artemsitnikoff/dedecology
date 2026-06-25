"""Пользователи: список, создание-приглашение, удаление (SPEC §3 /users)."""

import secrets
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import ConflictError, ForbiddenError, NotFoundError
from ..core.security import get_password_hash
from ..models import User
from ..schemas.user import UserCreate, UserListItem
from .audit import audit


async def list_users(session: AsyncSession) -> list[UserListItem]:
    """Все пользователи (сортировка по ФИО) для экрана Настроек."""
    result = await session.execute(select(User).order_by(User.fio))
    users = result.scalars().all()
    return [UserListItem.model_validate(u) for u in users]


async def get_user(session: AsyncSession, user_id: UUID) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("Пользователь")
    return user


async def create_invite(
    session: AsyncSession,
    user_data: UserCreate,
    actor_user_id: UUID,
) -> tuple[User, str]:
    """Создаёт приглашённого пользователя (status='invited') с временным паролем.

    Письмо НЕ отправляется (честно подписываем на фронте) — пароль возвращается один раз.
    Возвращает (user, temp_password). Дубликат email → 409 CONFLICT.
    """
    existing = await session.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("Пользователь с таким email уже существует")

    temp_password = secrets.token_urlsafe(12)

    user = User(
        email=user_data.email,
        password_hash=get_password_hash(temp_password),
        fio=user_data.fio,
        role=user_data.role,
        status="invited",
        is_active=True,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        # Защита от гонки на уникальном email.
        # Откат ДО raise — иначе общая сессия остаётся в pending-rollback
        # и commit в роутере падает с PendingRollbackError.
        await session.rollback()
        raise ConflictError("Пользователь с таким email уже существует")

    await audit(
        session,
        action="create",
        entity_type="user",
        entity_id=user.id,
        after={
            "email": user.email,
            "fio": user.fio,
            "role": user.role,
            "status": user.status,
        },
        actor_user_id=actor_user_id,
    )
    return user, temp_password


async def delete_user(
    session: AsyncSession,
    user_id: UUID,
    actor_user_id: UUID,
) -> None:
    """Удаляет пользователя. Нельзя удалить admin-роль и нельзя удалить самого себя."""
    user = await get_user(session, user_id)

    if user.id == actor_user_id:
        raise ForbiddenError("Нельзя удалить самого себя")

    if user.role == "admin":
        raise ForbiddenError("Нельзя удалить администратора")

    await audit(
        session,
        action="delete",
        entity_type="user",
        entity_id=user.id,
        before={
            "email": user.email,
            "fio": user.fio,
            "role": user.role,
            "status": user.status,
        },
        actor_user_id=actor_user_id,
    )

    await session.delete(user)
    await session.flush()


async def update_profile(
    session: AsyncSession,
    user: User,
    fio: str,
    actor_user_id: UUID,
) -> User:
    """Обновляет ФИО текущего пользователя (PATCH /profile)."""
    before = {"fio": user.fio}
    user.fio = fio
    await session.flush()
    await audit(
        session,
        action="update",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after={"fio": user.fio},
        actor_user_id=actor_user_id,
    )
    return user


async def reset_own_password(
    session: AsyncSession,
    user: User,
    new_password: str,
    actor_user_id: UUID,
) -> None:
    """Смена собственного пароля без проверки текущего (ТЗ §9.1)."""
    user.password_hash = get_password_hash(new_password)
    await session.flush()
    await audit(
        session,
        action="password_reset",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=actor_user_id,
    )
