import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Volunteer(Base, TimestampMixin):
    """Волонтёр мобильного приложения — ОТДЕЛЬНАЯ сущность от пользователей админки.

    Не имеет ролей/супер-админа/локаута админ-юзера: у волонтёра свой JWT
    (typ="volunteer"), свои /volunteer/* эндпоинты и справочник /volunteers в админке
    (только просмотр + блокировка/удаление). Логин возможен лишь после подтверждения
    почты (email_verified) и при активной учётке (is_active — флаг блокировки админом).
    """

    __tablename__ = "volunteers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Уникальный обязательный email (подтверждается по ссылке из письма).
    # unique + index → единый уникальный индекс ix_volunteers_email.
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Телефон необязателен (проставляется на онбординге после первого входа).
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Почта подтверждена (до подтверждения вход запрещён — 403 EMAIL_NOT_VERIFIED).
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Флаг блокировки волонтёра админом (false → вход запрещён 403 BLOCKED).
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    # «Последняя авторизация»: обновляется при успешном логине и при любом запросе
    # волонтёра по его JWT (в get_current_volunteer, с троттлингом ≤1 раз/мин).
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
