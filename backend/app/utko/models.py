"""Модели УТКО-совместимого API (ядро приёма данных посещения МНО).

Отдельные таблицы с префиксом `utko_` — хранилище для входящих/исходящих данных интеграции,
изолированы от доменных таблиц приложения. UUID PK (gen_random_uuid()), TIMESTAMP(tz)=UTC.

Все три модели наследуют общий Base (app/models/base.py), поэтому metadata у них общая с
остальным приложением — create_all/alembic видят их вместе с доменными таблицами.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Text, text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from ..models.base import Base, CreatedAtMixin


class UtkoTruckVisitEvent(Base, CreatedAtMixin):
    """Событие посещения МНО мусоровозом — выдаётся клиенту через truck-visit-events/query.

    В ядре-скелете таблица наполняется извне (сид/будущая интеграция); эндпоинт query
    честно отдаёт то, что в ней есть (пусто → count 0). Ключ выборки/сортировки — create_date.
    """

    __tablename__ = "utko_truck_visit_event"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    mno_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    is_empty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    photo_link_before: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    photo_link_after: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    # create_date — момент появления записи во ФГИС (ключ фильтра query); server_default now().
    create_date: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    # created_at — из CreatedAtMixin (служебный момент вставки в нашу БД).


class UtkoTruckVisitConfirm(Base, CreatedAtMixin):
    """Подтверждение опустошения контейнера по событию посещения (приём confirm).

    Храним результат проверки оператором: подтверждено/нет + при неподтверждении — массив
    нарушений events (JSONB, список {eventType, typeContainer?}) и текст problem.
    """

    __tablename__ = "utko_truck_visit_confirm"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Событие, к которому относится подтверждение (→ utko_truck_visit_event.id). Индекс
    # для upsert по event_id. Жёсткого FK нет: приём данных не должен падать каскадом.
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    is_empty_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    problem: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Массив нарушений [{eventType, typeContainer?}] — как пришёл (JSONB), nullable.
    events: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    create_date: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class UtkoVideoEvent(Base, CreatedAtMixin):
    """Событие обработки видеопотока (приём video-events).

    id (UUID) отдаётся клиенту как videoEventUuid в ответе. external_event_id — ИД события
    на стороне клиента (nullable, по контракту необязателен).
    """

    __tablename__ = "utko_video_event"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    mno_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # externalEventId — в доке тип «uuid», но пример ответа echo-ит произвольную строку «123»
    # (таблица ответа — «строка»): храним как TEXT и возвращаем verbatim (строгий UUID-парс
    # дал бы ложный 422 на валидном по доке значении).
    external_event_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    photo_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Массив событий [{eventType, typeContainer?}] — как пришёл (JSONB), nullable/пустой.
    events: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    create_date: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
