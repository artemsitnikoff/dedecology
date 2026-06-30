"""Схемы справочника «Регионы» (субъекты РФ) и федеральных округов."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .base import ORMBase


class RegionListItem(ORMBase):
    """Строка справочника регионов. fed_code/fed_name резолвятся из FEDERAL_DISTRICTS,
    mno_count/incidents_count — подсчитываются сервисом."""
    code: str
    name: str
    fed: int
    fed_code: str
    fed_name: str
    operators: list[str]
    active: bool
    last_sync: Optional[datetime] = None
    mno_count: int
    incidents_count: int


class RegionDetail(RegionListItem):
    """Карточка региона — те же поля, что и в списке (контракт)."""
    pass


class RegionCreate(BaseModel):
    """Создание региона. active=true проставляется сервисом."""
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    fed: int
    operators: list[str] = Field(default_factory=list)


class FederalDistrict(BaseModel):
    """Элемент справочника федеральных округов."""
    id: int
    code: str
    name: str
