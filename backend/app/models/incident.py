import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, CheckConstraint, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Источник обращения: 'max' (мессенджер Макс) | 'form' (Яндекс форма)
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    # Статус триажа: 'new' | 'found' | 'none' | 'exported'
    status: Mapped[str] = mapped_column(
        String(12),
        nullable=False,
        server_default=text("'new'"),
    )
    fio: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    region: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    city: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    # улица/дом (+ «Радар №…» для Макс)
    street: Mapped[str] = mapped_column(String(500), nullable=False, server_default=text("''"))
    # "lat, lon" текстом
    coords: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("''"))
    # дата/время фотофиксации (ключ сортировки + фильтра периода)
    photo_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    photos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    # list[str] — пути/data-URL фото (сид: placeholder-картинки)
    photo_urls: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # id сообщения Макс (ссылка https://max.ru/m/{msg} строится на фронте)
    msg: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    # Форма «баки раздельного сбора» (в модели есть, в таблице скрыто по ТЗ §11)
    bins: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # «поступило»
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    # Момент успешной отправки уведомления в группу Макс (NULL → ещё не отправлено).
    notified_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # Сгенерированная цитата о природе (сохраняется для повторного показа в группе).
    quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("source IN ('max', 'form')", name="check_incident_source"),
        CheckConstraint(
            "status IN ('new', 'found', 'none', 'exported')",
            name="check_incident_status",
        ),
    )
