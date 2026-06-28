from pydantic import BaseModel
from typing import Literal, Optional
from uuid import UUID
from datetime import datetime

from .base import ORMBase

IncidentStatus = Literal["new", "found", "none", "exported"]
IncidentSource = Literal["max", "form"]


class IncidentListItem(ORMBase):
    """Строка таблицы инцидентов."""
    id: UUID
    source: IncidentSource
    status: IncidentStatus
    fio: str
    region: str
    city: str
    street: str
    coords: str
    comment: str | None = None
    photo_time: Optional[datetime]
    photos: int
    photo_urls: list[str]
    msg: Optional[str]
    msg_url: str | None = None
    received_at: datetime


class IncidentDetail(ORMBase):
    """Полная карточка инцидента (включая bins)."""
    id: UUID
    source: IncidentSource
    status: IncidentStatus
    fio: str
    region: str
    city: str
    street: str
    coords: str
    comment: str | None = None
    photo_time: Optional[datetime]
    photos: int
    photo_urls: list[str]
    msg: Optional[str]
    msg_url: str | None = None
    bins: Optional[bool]
    received_at: datetime
    created_at: datetime
    updated_at: datetime


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus


class BulkStatusUpdate(BaseModel):
    ids: list[UUID]
    status: IncidentStatus


class ExportSelection(BaseModel):
    """Тело POST /incidents/export — id выбранных инцидентов."""
    ids: list[UUID]


class BulkStatusResult(BaseModel):
    updated: int


class BulkDelete(BaseModel):
    ids: list[UUID]


class BulkDeleteResult(BaseModel):
    deleted: int


class FunnelCounts(BaseModel):
    all: int
    new: int
    found: int
    none: int
    exported: int


class PendingNotifyItem(ORMBase):
    """Инцидент, ожидающий уведомления в группу Макс (notified_at IS NULL)."""
    id: UUID
    source: IncidentSource
    fio: str
    region: str
    city: str
    street: str
    coords: str
    comment: str | None = None
    photo_time: Optional[datetime]
    photo_urls: list[str]
    msg: Optional[str]
    msg_url: str | None = None
    quote: Optional[str]


class PendingNotifyResponse(BaseModel):
    incidents: list[PendingNotifyItem]


class MarkNotified(BaseModel):
    ids: list[UUID]


class MarkNotifiedResult(BaseModel):
    marked: int
