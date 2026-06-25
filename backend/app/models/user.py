import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, CheckConstraint, Integer, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    fio: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'user'"),
    )
    # 'active' | 'invited' — invited переводится в active при первом успешном входе
    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'active'"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    # Защита от брутфорса пароля (account lockout через БД, работает при 2+ воркерах)
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="check_user_role"),
        CheckConstraint("status IN ('active', 'invited')", name="check_user_status"),
    )
