import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, Boolean, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class SmtpSettings(Base, TimestampMixin):
    """Настройки почтового сервера (SMTP) — ЕДИНСТВЕННАЯ строка на арендатора.

    Single-tenant: во всей БД существует не более одной строки этой таблицы
    (get-or-create в сервисе). Пароль хранится ТОЛЬКО зашифрованным (Fernet) в
    `password_enc` и НИКОГДА не отдаётся наружу — GET-статус его не включает.

    `status`: 'disconnected' по умолчанию и после любого сохранения конфига;
    'connected' — только после УСПЕШНОЙ тестовой отправки. `last_test_*` фиксируют
    исход последнего теста (в т.ч. ошибку — для показа в UI).
    """

    __tablename__ = "smtp_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    host: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    port: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # Режим шифрования: 'ssl' | 'tls' | 'none'.
    encryption: Mapped[str] = mapped_column(String(8), nullable=False, server_default=text("'ssl'"))
    username: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    # Пароль SMTP в виде шифртекста Fernet. НАРУЖУ НИКОГДА не отдаётся.
    password_enc: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    from_email: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    from_name: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    # Состояние подключения: 'disconnected' | 'connected'.
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'disconnected'"))
    last_test_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_test_ok: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    last_test_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
