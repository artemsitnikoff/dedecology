"""Эндпоинты редактируемого справочника «Типы инцидентов» (админка).

GET — авторизованным пользователям (просмотр справочника на странице). Мутации
(POST/PATCH/DELETE) — только админ (Depends(require_admin)). code типа неизменяем:
правим только label/sort_order. Удаление НЕ трогает инциденты (слабая связь по коду).
Ошибки — через AppError-исключения сервиса (ConflictError/NotFoundError).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.permissions import require_admin
from ...database import get_db
from ...deps import get_current_user
from ...models import User
from ...schemas.incident_type import (
    IncidentTypeCreate,
    IncidentTypeItem,
    IncidentTypeUpdate,
)
from ...services import incident_type as incident_type_service

router = APIRouter()

_TAG = "Справочники"


@router.get("", response_model=list[IncidentTypeItem], tags=[_TAG])
async def list_incident_types(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Полный справочник типов инцидента [{id, code, label, sort_order}] для страницы."""
    return await incident_type_service.list_types(session)


@router.post("", response_model=IncidentTypeItem, status_code=201, tags=[_TAG])
async def create_incident_type(
    payload: IncidentTypeCreate,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Создаёт тип инцидента (require_admin). code генерится, если не задан."""
    incident_type = await incident_type_service.create_type(
        session,
        label=payload.label,
        code=payload.code,
        sort_order=payload.sort_order,
    )
    await session.commit()
    return incident_type


@router.patch("/{type_id}", response_model=IncidentTypeItem, tags=[_TAG])
async def update_incident_type(
    type_id: UUID,
    payload: IncidentTypeUpdate,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Изменяет label/sort_order (require_admin). code неизменяем."""
    incident_type = await incident_type_service.update_type(
        session,
        type_id,
        label=payload.label,
        sort_order=payload.sort_order,
    )
    await session.commit()
    return incident_type


@router.delete("/{type_id}", status_code=204, tags=[_TAG])
async def delete_incident_type(
    type_id: UUID,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Удаляет тип (require_admin). Инциденты с этим кодом остаются (покажут «—»)."""
    await incident_type_service.delete_type(session, type_id)
    await session.commit()
    return Response(status_code=204)
