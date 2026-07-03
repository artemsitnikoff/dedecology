import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, CheckConstraint, Float, Integer, Text, text
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
    # Числовые координаты (миграция 0009): дублируют coords для быстрого bbox-фильтра
    # карты по индексу ix_incidents_lat_lon. NULL — coords пусты/невалидны.
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Реестровый № выбранного на карте публичной формы МНО (места накопления отходов).
    # NULL — МНО не выбрано (адрес введён вручную / Макс-бот / старые инциденты).
    mno_reg: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # ПРОЧАЯ не-адресная информация из свободного текста обращения: «Радар №…»,
    # ФИО заявителя (если есть в тексте), описание проблемы («Баки раздельного
    # сбора отсутствуют»), заметки. Раньше AI это выкидывал; NULL — нет/не извлечено.
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Тип инцидента: КОД из справочника services/incident_types.py (напр. «fire»).
    # Заполняется публичной формой волонтёра; русская подпись резолвится по коду на
    # фронте. NULL — тип не задан (старые инциденты / Макс-бот, где типа нет).
    incident_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # дата/время фотофиксации (ключ сортировки + фильтра периода)
    photo_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    photos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    # list[str] — пути/data-URL фото (сид: placeholder-картинки)
    photo_urls: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # id сообщения Макс (внутренний mid; трейс/поиск — ссылка из него НЕ строится)
    msg: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    # Готовый полный https-URL сообщения Макс (Message.url), напр.
    # "https://max.ru/c/-757…/AZ8…". Для лички с ботом обычно отсутствует (NULL).
    msg_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
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
