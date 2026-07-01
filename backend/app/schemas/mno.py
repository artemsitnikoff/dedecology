"""Схемы МНО (места накопления отходов)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .base import ORMBase


class MnoListItem(ORMBase):
    """Строка реестра МНО. region_name резолвится из справочника регионов."""
    id: UUID
    reg: str
    name: str
    region_code: str
    region_name: str
    city: str
    address: str
    coords: str
    fgis_id: Optional[str] = None
    synced: bool
    sync_date: Optional[datetime] = None
    incidents: int


class MnoDetail(MnoListItem):
    """Карточка МНО — те же поля, что и в списке (контракт)."""
    pass


class MnoCreate(BaseModel):
    """Создание МНО вручную. Обязательны только name + coords.

    synced=false, fgis_id=null, incidents=0 проставляются сервисом — НЕ из тела.
    """
    name: str = Field(min_length=1)
    coords: str = Field(min_length=1)
    reg: str = ""
    region_code: str = ""
    city: str = ""
    address: str = ""


class MnoSyncResult(BaseModel):
    """Итог ЗАГЛУШКИ синхронизации с ФГИС: сколько помечено / всего МНО."""
    synced: int
    total: int


class MnoPoint(ORMBase):
    """Лёгкая точка МНО для карты: id + координаты «lat, lon» + название."""
    id: UUID
    coords: str
    name: str


class MnoPointsResponse(BaseModel):
    """Точки МНО для карты (отдельный лёгкий эндпоинт, без пагинации).

    total — всего МНО по текущему фильтру; points — первые не более лимита точек
    с непустыми координатами; capped=True — total превысил лимит и points обрезаны.
    """
    points: list[MnoPoint]
    total: int
    capped: bool
