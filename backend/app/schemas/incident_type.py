"""Схемы редактируемого справочника «Типы инцидентов»."""

import uuid

from pydantic import BaseModel, Field

from .base import ORMBase


class IncidentTypeItem(ORMBase):
    """Строка справочника типов инцидента (для страницы админки)."""

    id: uuid.UUID
    code: str
    label: str
    sort_order: int


class IncidentTypeCreate(BaseModel):
    """Создание типа. code необязателен (пуст → сервис сгенерит автокод);
    sort_order необязателен (пуст → в конец списка)."""

    label: str = Field(min_length=1, max_length=500)
    code: str | None = Field(default=None, max_length=64)
    sort_order: int | None = None


class IncidentTypeUpdate(BaseModel):
    """Изменение типа: правим только label/sort_order. code неизменяем."""

    label: str | None = Field(default=None, min_length=1, max_length=500)
    sort_order: int | None = None
