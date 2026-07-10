"""Эндпоинты редактируемого справочника «Стоп-лист почтовых доменов» (админка).

Все роуты — только админ (Depends(require_admin)): и просмотр, и мутации. Домены
блокируют регистрацию волонтёра по почтовому домену (services/volunteer.register).
Ошибки — через AppError-исключения сервиса (ConflictError/NotFoundError/ValidationError).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.permissions import require_admin
from ...database import get_db
from ...schemas.blocked_domain import BlockedDomainCreate, BlockedDomainItem
from ...services import blocked_domain as blocked_domain_service

router = APIRouter()

_TAG = "Справочники"


@router.get("", response_model=list[BlockedDomainItem], tags=[_TAG])
async def list_blocked_domains(
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Полный стоп-лист доменов [{id, domain, created_at}] (require_admin)."""
    return await blocked_domain_service.list_domains(session)


@router.post("", response_model=BlockedDomainItem, status_code=201, tags=[_TAG])
async def create_blocked_domain(
    payload: BlockedDomainCreate,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Добавляет домен в стоп-лист (require_admin). Значение нормализуется сервисом."""
    blocked = await blocked_domain_service.create_domain(session, domain=payload.domain)
    await session.commit()
    return blocked


@router.delete("/{domain_id}", status_code=204, tags=[_TAG])
async def delete_blocked_domain(
    domain_id: UUID,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Удаляет домен из стоп-листа (require_admin)."""
    await blocked_domain_service.delete_domain(session, domain_id)
    await session.commit()
    return Response(status_code=204)
