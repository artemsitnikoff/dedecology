"""Админ-справочник «Волонтёры», prefix /volunteers. Гейт require_admin — в router.py.

Только просмотр + блокировка/разблокировка (is_active) + удаление. Волонтёры — отдельная
сущность от пользователей админки (users): здесь ими управляют, но не аутентифицируются.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.volunteer import VolunteerListItem, VolunteerSetActive
from ...services import volunteer as volunteer_service

router = APIRouter()

_TAG = "Справочники"


@router.get("", response_model=list[VolunteerListItem], tags=[_TAG])
async def list_volunteers(
    session: AsyncSession = Depends(get_db),
):
    """Список волонтёров (новые сверху) для справочника «Волонтёры»."""
    volunteers = await volunteer_service.list_all(session)
    return [VolunteerListItem.model_validate(v) for v in volunteers]


@router.patch("/{volunteer_id}/active", response_model=VolunteerListItem, tags=[_TAG])
async def set_volunteer_active(
    volunteer_id: UUID,
    data: VolunteerSetActive,
    session: AsyncSession = Depends(get_db),
):
    """Блокировка/разблокировка волонтёра (is_active). Нет волонтёра → 404."""
    volunteer = await volunteer_service.set_active(session, volunteer_id, data.is_active)
    await session.commit()
    return VolunteerListItem.model_validate(volunteer)


@router.delete("/{volunteer_id}", status_code=204, tags=[_TAG])
async def delete_volunteer(
    volunteer_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Удаляет волонтёра. Нет волонтёра → 404."""
    await volunteer_service.delete(session, volunteer_id)
    await session.commit()
    return Response(status_code=204)
