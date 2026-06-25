"""Эндпоинты управления пользователями (SPEC §3 /users). Гейт require_admin — в router.py."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...deps import get_current_user
from ...models import User
from ...schemas.user import UserCreate, UserCreateResult, UserListItem, UserShort
from ...services.user import create_invite, delete_user, list_users

router = APIRouter()


@router.get("", response_model=list[UserListItem])
async def get_users(
    session: AsyncSession = Depends(get_db),
):
    """Список всех пользователей для экрана Настроек."""
    return await list_users(session)


@router.post("", response_model=UserCreateResult, status_code=201)
async def invite_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создаёт приглашённого пользователя, возвращает временный пароль один раз.

    Письмо НЕ отправляется (на фронте честно подписываем).
    """
    user, temp_password = await create_invite(session, user_data, current_user.id)
    await session.commit()
    result = UserShort.model_validate(user).model_dump()
    result["status"] = user.status
    result["temp_password"] = temp_password
    return UserCreateResult(**result)


@router.delete("/{user_id}", status_code=204)
async def remove_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удаляет пользователя. Нельзя удалить admin-роль и самого себя."""
    await delete_user(session, user_id, current_user.id)
    await session.commit()
    return Response(status_code=204)
