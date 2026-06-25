"""Эндпоинты инцидентов (SPEC §3 /incidents).

ВАЖНО: статические роуты (/funnel, /export, /bulk-status) объявлены ДО /{id},
иначе FastAPI трактует литерал как UUID-параметр пути → 422.
"""

from datetime import date, datetime
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...deps import get_current_user
from ...models import User
from ...schemas.base import Paginated
from ...schemas.incident import (
    BulkStatusResult,
    BulkStatusUpdate,
    ExportSelection,
    FunnelCounts,
    IncidentDetail,
    IncidentListItem,
    IncidentStatusUpdate,
)
from ...services import incident as incident_service
from ...services.export import build_xlsx

router = APIRouter()

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(content: bytes, filename: str) -> Response:
    """Отдаёт .xlsx с корректным UTF-8 filename* (кириллица)."""
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": disposition},
    )


def _as_datetime(d: date | None) -> datetime | None:
    if d is None:
        return None
    return datetime(d.year, d.month, d.day)


@router.get("", response_model=Paginated[IncidentListItem])
async def list_incidents(
    search: str | None = Query(None),
    source: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    sort: str = Query("date"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список инцидентов с фильтрами/сортировкой/пагинацией."""
    return await incident_service.list_incidents(
        session,
        search=search,
        source=source,
        status=status,
        date_from=_as_datetime(date_from),
        date_to=_as_datetime(date_to),
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get("/funnel", response_model=FunnelCounts)
async def get_funnel(
    search: str | None = Query(None),
    source: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Счётчики чипов воронки (honor search/source/period, НЕ status)."""
    return await incident_service.funnel_counts(
        session,
        search=search,
        source=source,
        date_from=_as_datetime(date_from),
        date_to=_as_datetime(date_to),
    )


@router.get("/export")
async def export_incidents_get(
    search: str | None = Query(None),
    source: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    sort: str = Query("date"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт всего отфильтрованного набора в .xlsx."""
    rows = await incident_service.list_for_export(
        session,
        search=search,
        source=source,
        status=status,
        date_from=_as_datetime(date_from),
        date_to=_as_datetime(date_to),
        sort=sort,
        order=order,
    )
    return _xlsx_response(build_xlsx(rows), "Инциденты_ДедЭколог.xlsx")


@router.post("/export")
async def export_incidents_post(
    payload: ExportSelection,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт выбранных инцидентов в .xlsx."""
    rows = await incident_service.list_by_ids(session, payload.ids)
    return _xlsx_response(build_xlsx(rows), "Инциденты_ДедЭколог_выбранные.xlsx")


@router.post("/bulk-status", response_model=BulkStatusResult)
async def bulk_status(
    payload: BulkStatusUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Массовая смена статуса (powers «Пометить Выгружен»)."""
    updated = await incident_service.bulk_status(
        session, payload.ids, payload.status, current_user.id
    )
    await session.commit()
    return BulkStatusResult(updated=updated)


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Карточка инцидента (включая bins)."""
    incident = await incident_service.get_incident(session, incident_id)
    return IncidentDetail.model_validate(incident)


@router.patch("/{incident_id}/status", response_model=IncidentDetail)
async def update_incident_status(
    incident_id: UUID,
    payload: IncidentStatusUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Смена статуса одного инцидента."""
    incident = await incident_service.set_status(
        session, incident_id, payload.status, current_user.id
    )
    await session.commit()
    return IncidentDetail.model_validate(incident)
