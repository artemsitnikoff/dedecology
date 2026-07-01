"""Эндпоинты управления пользователями (SPEC §3 /users). Гейт require_admin — в router.py."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...deps import get_current_user
from ...models import User
from ...schemas.user import PasswordReset, UserCreate, UserListItem
from ...services.user import create_user, delete_user, list_users, set_user_password

router = APIRouter()


@router.get(
    "",
    response_model=list[UserListItem],
    tags=["Управление пользователями (вне мобильного API)"],
)
async def get_users(
    session: AsyncSession = Depends(get_db),
):
    """Список всех пользователей для экрана Настроек."""
    return await list_users(session)


@router.post(
    "",
    response_model=UserListItem,
    status_code=201,
    tags=["Управление пользователями (вне мобильного API)"],
)
async def create_user_endpoint(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создаёт активного пользователя с заданным админом паролем (инвайт-флоу убран)."""
    user = await create_user(session, user_data, current_user.id)
    await session.commit()
    return UserListItem.model_validate(user)


@router.post(
    "/{user_id}/password",
    status_code=204,
    tags=["Управление пользователями (вне мобильного API)"],
)
async def set_password(
    user_id: UUID,
    data: PasswordReset,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Задаёт/сбрасывает пароль пользователю. Супер-админу — запрещено (403)."""
    await set_user_password(session, user_id, data.new_password, current_user.id)
    await session.commit()
    return Response(status_code=204)


@router.delete(
    "/{user_id}",
    status_code=204,
    tags=["Управление пользователями (вне мобильного API)"],
)
async def remove_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удаляет пользователя. Нельзя удалить супер-админа, admin-роль и самого себя."""
    await delete_user(session, user_id, current_user.id)
    await session.commit()
    return Response(status_code=204)
