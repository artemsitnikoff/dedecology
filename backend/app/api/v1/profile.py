"""Эндпоинты профиля текущего пользователя (SPEC §3 /profile)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...deps import get_current_actor, get_current_user
from ...models import User, Volunteer
from ...schemas.auth import UserMe
from ...schemas.base import MessageResult
from ...schemas.user import PasswordReset, ProfileUpdate
from ...services.user import reset_own_password, update_profile
from ...services.volunteer import change_own_password as volunteer_change_own_password

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
    actor=Depends(get_current_actor),
):
    """Смена собственного пароля (без проверки текущего, ТЗ §9.1).

    Принимает ОБА типа токена: admin access-токен (User) и volunteer-токен (Volunteer).
    По типу actor выбираем нужный сервис — мобильное приложение волонтёра шлёт свой
    пароль сюда же, а не на отдельный эндпоинт."""
    if isinstance(actor, Volunteer):
        await volunteer_change_own_password(session, actor, data.new_password)
    else:
        await reset_own_password(session, actor, data.new_password, actor.id)
    await session.commit()
    return MessageResult(message="Пароль обновлён")
