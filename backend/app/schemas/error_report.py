"""Схемы технических ошибок мобильного приложения."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .base import ORMBase


class ErrorReportCreate(BaseModel):
    """Вход от приложения — контекст технической ошибки при сбое."""

    error_type: str = Field(min_length=1, max_length=64)
    message: str | None = Field(default=None, max_length=500)
    app_version: str | None = Field(default=None, max_length=64)
    user_action: str | None = None
    platform: str | None = Field(default=None, max_length=32)
    technical: dict | None = None
    occurred_at: datetime | None = None
    volunteer_email: str | None = Field(default=None, max_length=255)


class ErrorReportCreated(BaseModel):
    """Ответ приложению на регистрацию ошибки."""

    id: UUID
    code: str
    created_at: datetime
    emailed: bool


class ErrorReportItem(ORMBase):
    """Строка списка админки (без тяжёлых полей)."""

    id: UUID
    code: str
    error_type: str
    message: str | None
    app_version: str | None
    platform: str | None
    volunteer_email: str | None
    occurred_at: datetime | None
    created_at: datetime
    emailed: bool


class ErrorReportDetail(ErrorReportItem):
    """Карточка ошибки — со всеми деталями."""

    user_action: str | None
    technical: dict | None
    email_error: str | None
