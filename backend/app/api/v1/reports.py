"""Эндпоинты отчётов (история Excel-выгрузок обращений).

Тонкий слой: приём запроса → сервис → схема. Генерация синхронная (без arq).
Доступ — любой авторизованный (admin И user), как экспорт обращений.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...deps import get_current_user
from ...models import User
from ...schemas.base import MessageResult, Paginated
from ...schemas.report import ReportCreateRequest, ReportListItem
from ...services import report as report_service
from .incidents import _public_base, _xlsx_response

router = APIRouter()


@router.post(
    "/incidents",
    response_model=ReportListItem,
    status_code=201,
    tags=["Отчёты"],
)
async def create_incidents_report(
    payload: ReportCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Синхронно формирует .xlsx по обращениям (фильтр или выбранные ids), сохраняет на диск."""
    report = await report_service.create_incidents_report(
        session, current_user, base_url=_public_base(request), req=payload
    )
    await session.commit()
    return ReportListItem.model_validate(report)


@router.get("", response_model=Paginated[ReportListItem], tags=["Отчёты"])
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """История сформированных отчётов (новейшие первыми)."""
    return await report_service.list_reports(session, page=page, page_size=page_size)


@router.get("/{report_id}/download", tags=["Отчёты"])
async def download_report(
    report_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отдаёт реально сохранённый на диске файл отчёта; нет строки/файла → 404."""
    path, filename = await report_service.get_for_download(session, report_id)
    return _xlsx_response(path.read_bytes(), filename)


@router.delete("/{report_id}", response_model=MessageResult, tags=["Отчёты"])
async def delete_report(
    report_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удаляет отчёт (строку + файл на диске)."""
    await report_service.delete_report(session, report_id, current_user)
    await session.commit()
    return MessageResult(message="Отчёт удалён")
