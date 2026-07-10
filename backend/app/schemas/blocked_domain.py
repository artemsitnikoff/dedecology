"""Схемы редактируемого справочника «Стоп-лист почтовых доменов»."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from .base import ORMBase


class BlockedDomainItem(ORMBase):
    """Строка стоп-листа доменов (для страницы админки)."""

    id: uuid.UUID
    domain: str
    created_at: datetime


class BlockedDomainCreate(BaseModel):
    """Добавление домена в стоп-лист. Сервис нормализует значение (lowercase/@)."""

    domain: str = Field(min_length=1, max_length=255)
