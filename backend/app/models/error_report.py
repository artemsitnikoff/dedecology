import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ErrorReport(Base, TimestampMixin):
    """Техническая ошибка мобильного приложения (централизованный журнал).

    Приложение при сбое собирает контекст (тип, действие пользователя, версия,
    тех.данные) и шлёт его на сервер (POST /intake/error-report). Сервер регистрирует
    ошибку с уникальным кодом, пишет в лог-систему, сохраняет строку сюда и шлёт письмо
    в техподдержку (SUPPORT_EMAIL). emailed/email_error фиксируют ЧЕСТНЫЙ исход отправки.
    """

    __tablename__ = "error_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Уникальный код ошибки, напр. "ERR-A1B2C3D4" — им клиент/поддержка ссылаются на инцидент.
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # Тип ошибки: "server"|"auth"|"photo_upload"|"other" или свободная строка.
    error_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Понятное человекочитаемое описание (напр. «Серверная ошибка»).
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Версия мобильного приложения.
    app_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Что пользователь делал перед сбоем.
    user_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Платформа: "android"|"ios" и т.п.
    platform: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Тех.данные: stacktrace / запрос / устройство и пр. (произвольный JSON).
    technical: Mapped[dict] = mapped_column(
        JSONB, nullable=True, server_default=text("'{}'::jsonb")
    )
    # Время сбоя на клиенте (ISO из приложения); отличается от created_at (приём сервером).
    occurred_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # Email волонтёра, если известен на клиенте.
    volunteer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Ушло ли письмо в техподдержку.
    emailed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Честный текст ошибки отправки письма (если не ушло) — БЕЗ фейка.
    email_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # created_at / updated_at — из TimestampMixin.
