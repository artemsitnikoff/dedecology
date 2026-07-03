"""Эндпоинты МНО (места накопления отходов).

ВАЖНО: статические роуты (/export, /sync) объявлены ДО /{mno_id}, иначе FastAPI
трактует литерал как UUID-параметр пути → 422.

ЗАГЛУШКА: синхронизация с ФГИС (/sync, /{id}/sync) — локальная, без внешних запросов
(см. services/mno.py).
"""

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...deps import get_current_actor, get_current_user
from ...models import User
from ...schemas.base import Paginated
from ...schemas.mno import (
    MnoCreate,
    MnoDetail,
    MnoListItem,
    MnoPointsResponse,
    MnoSyncResult,
)
from ...services import mno as mno_service
from ...services.mno_export import build_mno_xlsx

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


@router.get("", response_model=Paginated[MnoListItem], tags=["Карта и МНО"])
async def list_mno(
    search: str | None = Query(None),
    region: str | None = Query(None),
    synced: bool | None = Query(None),
    sort: str = Query("name"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    bbox: str | None = Query(
        None,
        description="Видимая область карты/гео «minLat,minLon,maxLat,maxLon» — вернуть "
        "только МНО этого кадра (ближайшие), как в /mno/points.",
    ),
    session: AsyncSession = Depends(get_db),
    _actor=Depends(get_current_actor),
):
    """Пагинированный реестр МНО с фильтрами region/synced/search + bbox + сортировкой.

    READ доступен и админу (веб), и волонтёру (мобильное приложение, карта площадок)."""
    return await mno_service.list_mno(
        session,
        search=search,
        region=region,
        synced=synced,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
        bbox=bbox,
    )


@router.get("/points", response_model=MnoPointsResponse, tags=["Карта и МНО"])
async def list_mno_points(
    search: str | None = Query(None),
    region: str | None = Query(None),
    synced: bool | None = Query(None),
    bbox: str | None = Query(
        None, description="Видимая область карты «minLat,minLon,maxLat,maxLon» (битый — игнор)"
    ),
    session: AsyncSession = Depends(get_db),
    _actor=Depends(get_current_actor),
):
    """Лёгкие координаты МНО для карты (обрезка до лимита на КАДР).

    bbox — видимая область: при зуме/панораме фронт перезапрашивает точки текущего
    кадра. Объявлен ДО /{mno_id} — статический роут раньше параметрического, иначе
    FastAPI трактует «points» как UUID → 422.
    """
    return await mno_service.list_points(
        session, search=search, region=region, synced=synced, bbox=bbox
    )


@router.get("/export", tags=["Экспорт (вне мобильного API)"])
async def export_mno(
    search: str | None = Query(None),
    region: str | None = Query(None),
    synced: bool | None = Query(None),
    sort: str = Query("name"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт отфильтрованного реестра МНО в .xlsx."""
    rows = await mno_service.list_for_export(
        session, search=search, region=region, synced=synced, sort=sort, order=order
    )
    return _xlsx_response(build_mno_xlsx(rows), "МНО_ЭкоПульс.xlsx")


@router.post("", response_model=MnoDetail, status_code=201, tags=["Добавление нового МНО"])
async def create_mno(
    payload: MnoCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Добавление МНО вручную (synced=false, fgis_id=null, incidents=0)."""
    mno = await mno_service.create_mno(session, payload, current_user.id)
    await session.commit()
    return mno


@router.post("/sync", response_model=MnoSyncResult, tags=["Карта и МНО"])
async def sync_all_mno(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ЗАГЛУШКА: помечает все ещё-не-synced МНО как синхронизированные с ФГИС."""
    result = await mno_service.sync_all(session, current_user.id)
    await session.commit()
    return result


@router.post("/{mno_id}/sync", response_model=MnoDetail, tags=["Карта и МНО"])
async def sync_one_mno(
    mno_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ЗАГЛУШКА: синхронизирует одно МНО с ФГИС (без внешних запросов)."""
    mno = await mno_service.sync_one(session, mno_id, current_user.id)
    await session.commit()
    return mno


@router.get("/{mno_id}", response_model=MnoDetail, tags=["Карточка МНО"])
async def get_mno(
    mno_id: UUID,
    session: AsyncSession = Depends(get_db),
    _actor=Depends(get_current_actor),
):
    """Карточка МНО (READ — админ или волонтёр)."""
    return await mno_service.get_mno(session, mno_id)
