"""Эндпоинты инцидентов (SPEC §3 /incidents).

ВАЖНО: статические роуты (/funnel, /export, /bulk-status) объявлены ДО /{id},
иначе FastAPI трактует литерал как UUID-параметр пути → 422.
"""

from datetime import date, datetime
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...deps import get_current_user
from ...models import User
from ...schemas.base import Paginated
from ...schemas.incident import (
    BulkDelete,
    BulkDeleteResult,
    BulkStatusResult,
    BulkStatusUpdate,
    ExportSelection,
    FunnelCounts,
    IncidentDetail,
    IncidentListItem,
    IncidentPointsResponse,
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


def _public_base(request: Request) -> str:
    """Схема+домен для абсолютных ссылок (ссылка на фото в .xlsx).

    За обратным прокси (Caddy/nginx) берём X-Forwarded-Proto/Host; запрос на экспорт
    всегда идёт из браузера админа, поэтому Host = публичный домен (ecopulse.reo.ru).
    """
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host}"


@router.get("", response_model=Paginated[IncidentListItem], tags=["Админский реестр"])
async def list_incidents(
    search: str | None = Query(None),
    source: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    region: str | None = Query(None),
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
        region=region,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get("/funnel", response_model=FunnelCounts, tags=["Админский реестр"])
async def get_funnel(
    search: str | None = Query(None),
    source: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    region: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Счётчики чипов воронки (honor search/source/period/region, НЕ status)."""
    return await incident_service.funnel_counts(
        session,
        search=search,
        source=source,
        date_from=_as_datetime(date_from),
        date_to=_as_datetime(date_to),
        region=region,
    )


@router.get("/regions", response_model=list[str], tags=["Админский реестр"])
async def list_regions(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """DISTINCT непустые регионы (А→Я) — наполняет дропдаун фильтра региона."""
    return await incident_service.list_regions(session)


@router.get("/points", response_model=IncidentPointsResponse, tags=["Админский реестр"])
async def list_incident_points(
    search: str | None = Query(None),
    source: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    region: str | None = Query(None),
    bbox: str | None = Query(
        None, description="Видимая область карты «minLat,minLon,maxLat,maxLon» (битый — игнор)"
    ),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Лёгкие координаты инцидентов для карты (обрезка до лимита на КАДР).

    Те же фильтры, что у списка (search/source/status/region/period), без sort/page,
    плюс bbox — видимая область: при зуме/панораме фронт перезапрашивает точки кадра.
    Объявлен ДО /{incident_id} — статический роут раньше параметрического, иначе
    FastAPI трактует «points» как UUID → 422.
    """
    return await incident_service.list_points(
        session,
        search=search,
        source=source,
        status=status,
        date_from=_as_datetime(date_from),
        date_to=_as_datetime(date_to),
        region=region,
        bbox=bbox,
    )


@router.get("/export", tags=["Экспорт (вне мобильного API)"])
async def export_incidents_get(
    request: Request,
    search: str | None = Query(None),
    source: list[str] | None = Query(None),
    status: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    region: str | None = Query(None),
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
        region=region,
        sort=sort,
        order=order,
    )
    return _xlsx_response(build_xlsx(rows, _public_base(request)), "Инциденты_ЭкоПульс.xlsx")


@router.post("/export", tags=["Экспорт (вне мобильного API)"])
async def export_incidents_post(
    request: Request,
    payload: ExportSelection,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт выбранных инцидентов в .xlsx."""
    rows = await incident_service.list_by_ids(session, payload.ids)
    return _xlsx_response(
        build_xlsx(rows, _public_base(request)), "Инциденты_ЭкоПульс_выбранные.xlsx"
    )


@router.post("/bulk-status", response_model=BulkStatusResult, tags=["Админский реестр"])
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


@router.post("/bulk-delete", response_model=BulkDeleteResult, tags=["Админский реестр"])
async def bulk_delete(
    payload: BulkDelete,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Массовое удаление инцидентов (hard delete + audit на каждый)."""
    deleted = await incident_service.bulk_delete(
        session, payload.ids, current_user.id
    )
    await session.commit()
    return BulkDeleteResult(deleted=deleted)


@router.get("/{incident_id}", response_model=IncidentDetail, tags=["Админский реестр"])
async def get_incident(
    incident_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Карточка инцидента (включая bins)."""
    incident = await incident_service.get_incident(session, incident_id)
    return IncidentDetail.model_validate(incident)


@router.patch(
    "/{incident_id}/status", response_model=IncidentDetail, tags=["Админский реестр"]
)
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
