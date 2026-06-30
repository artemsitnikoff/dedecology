"""Эндпоинты справочника «Регионы» (субъекты РФ) + справочник федеральных округов.

Регион адресуется по коду субъекта (строка, напр. "63") — НЕ uuid.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...deps import get_current_user
from ...models import User
from ...schemas.region import FederalDistrict, RegionCreate, RegionDetail, RegionListItem
from ...services import region as region_service
from ...services.federal_districts import list_federal_districts

router = APIRouter()
fed_router = APIRouter()


@router.get("", response_model=list[RegionListItem])
async def list_regions(
    search: str | None = Query(None),
    fed: list[int] | None = Query(None),
    sort: str = Query("code"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Справочник регионов: фильтры search/fed + сортировка, с mno_count/incidents_count."""
    return await region_service.list_regions(
        session, search=search, fed=fed, sort=sort, order=order
    )


@router.post("", response_model=RegionDetail, status_code=201)
async def create_region(
    payload: RegionCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Добавление региона (active=true). Дубликат кода → 409."""
    region = await region_service.create_region(session, payload, current_user.id)
    await session.commit()
    return region


@router.get("/{code}", response_model=RegionDetail)
async def get_region(
    code: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Карточка региона по коду субъекта."""
    return await region_service.get_region(session, code)


@fed_router.get("", response_model=list[FederalDistrict])
async def get_federal_districts(
    current_user: User = Depends(get_current_user),
):
    """Справочник федеральных округов РФ (нумерация ФГИС 1..8)."""
    return list_federal_districts()
