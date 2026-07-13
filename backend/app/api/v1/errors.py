"""Эндпоинты просмотра технических ошибок мобильного приложения (только admin).

Тонкий слой: приём запроса → сервис → схема. Приём ошибок от приложения живёт в
intake.py (POST /intake/error-report, защита X-Intake-Token); здесь — админ-просмотр
журнала. Гейт require_admin проставлен на include_router (см. router.py).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.base import Paginated
from ...schemas.error_report import ErrorReportDetail, ErrorReportItem
from ...services import error_report as error_report_service

router = APIRouter()


@router.get("", response_model=Paginated[ErrorReportItem], tags=["Ошибки приложения"])
async def list_error_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    """Журнал технических ошибок (новейшие первыми)."""
    return await error_report_service.list_error_reports(
        session, page=page, page_size=page_size
    )


@router.get("/{report_id}", response_model=ErrorReportDetail, tags=["Ошибки приложения"])
async def get_error_report(
    report_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Карточка ошибки со всеми деталями (тех.данные, действие пользователя, email_error)."""
    error = await error_report_service.get_error_report(session, report_id)
    return ErrorReportDetail.model_validate(error)
