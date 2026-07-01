"""Эндпоинты профиля текущего пользователя (SPEC §3 /profile)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...deps import get_current_user
from ...models import User
from ...schemas.auth import UserMe
from ...schemas.base import MessageResult
from ...schemas.user import PasswordReset, ProfileUpdate
from ...services.user import reset_own_password, update_profile

router = APIRouter()


@router.patch("", response_model=UserMe, tags=["Профиль пользователя"])
async def patch_profile(
    data: ProfileUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновляет Заявителя текущего пользователя."""
    user = await update_profile(session, current_user, data.fio, current_user.id)
    await session.commit()
    return UserMe.model_validate(user)


@router.post("/password", response_model=MessageResult, tags=["Профиль пользователя"])
async def change_password(
    data: PasswordReset,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Смена собственного пароля (без проверки текущего, ТЗ §9.1)."""
    await reset_own_password(session, current_user, data.new_password, current_user.id)
    await session.commit()
    return MessageResult(message="Пароль обновлён")
