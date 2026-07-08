"""Схемы отчётов (история Excel-выгрузок обращений)."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from .base import ORMBase


class ReportListItem(ORMBase):
    """Строка истории отчётов (и ответ на создание)."""

    id: UUID
    kind: str
    filename: str
    row_count: int
    size_bytes: int
    created_by_fio: str
    created_at: datetime


class ReportCreateRequest(BaseModel):
    """Запрос на формирование отчёта по обращениям.

    Если ids непуст — отчёт по выбранным обращениям (как POST /incidents/export).
    Иначе — по фильтру (как GET /incidents/export): search/source/status/region/период/сортировка.
    """

    # UUID (не str!): list_by_ids строит словарь по UUID-ключам и матчит эти id —
    # со строками матч всегда пуст → отчёт по выбранным получался на 0 строк.
    ids: list[UUID] = []
    search: str | None = None
    source: list[str] | None = None
    status: list[str] | None = None
    region: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    sort: str = "date"
    order: str = "desc"
