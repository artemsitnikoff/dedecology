"""Доступ к БД для УТКО-совместимого API (ядро).

Тонкий сервисный слой над моделями utko_* и доменной Mno. Роутеры валидируют вход и
вызывают эти функции; тесты офлайн патчат их целиком (session замокан AsyncMock).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Mno
from .models import UtkoTruckVisitConfirm, UtkoTruckVisitEvent, UtkoVideoEvent


# --- truck-visit-events/query ----------------------------------------------------


async def query_truck_visit_events(
    session: AsyncSession,
    *,
    from_date: datetime,
    to_date: datetime | None,
    take: int,
    skip: int,
) -> tuple[int, list[UtkoTruckVisitEvent]]:
    """Вернуть (count всего под фильтр, страница событий).

    Фильтр: create_date >= from_date [AND create_date < to_date]. Сортировка по create_date.
    Пагинация skip/take. С роутера take всегда 1..MAX_TAKE (кап в validate.validate_query) —
    безлимитного ответа не бывает; take <= 0 на прямом вызове = «без лимита» (защита — выше).
    """
    conds = [UtkoTruckVisitEvent.create_date >= from_date]
    if to_date is not None:
        conds.append(UtkoTruckVisitEvent.create_date < to_date)

    count_stmt = select(func.count()).select_from(UtkoTruckVisitEvent).where(*conds)
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(UtkoTruckVisitEvent)
        .where(*conds)
        .order_by(UtkoTruckVisitEvent.create_date)
    )
    if skip > 0:
        stmt = stmt.offset(skip)
    if take > 0:  # take <= 0 → без лимита (все под фильтр)
        stmt = stmt.limit(take)

    rows = (await session.execute(stmt)).scalars().all()
    return int(total), list(rows)


# --- truck-visit-events/confirm --------------------------------------------------


async def event_exists(session: AsyncSession, event_id: UUID) -> bool:
    """Есть ли событие посещения с таким id в БД (проверка п.3 Таблицы 2)."""
    stmt = select(UtkoTruckVisitEvent.id).where(UtkoTruckVisitEvent.id == event_id)
    return (await session.execute(stmt)).first() is not None


async def upsert_confirmation(session: AsyncSession, item: dict) -> UtkoTruckVisitConfirm:
    """Сохранить подтверждение по event_id (upsert: обновить существующее или создать)."""
    stmt = select(UtkoTruckVisitConfirm).where(
        UtkoTruckVisitConfirm.event_id == item["event_id"]
    )
    existing = (await session.execute(stmt)).scalars().first()
    events = item["events"] if item["events"] else None
    if existing is not None:
        existing.is_empty_confirmed = item["is_empty_confirmed"]
        existing.problem = item["problem"]
        existing.events = events
        return existing
    row = UtkoTruckVisitConfirm(
        event_id=item["event_id"],
        is_empty_confirmed=item["is_empty_confirmed"],
        problem=item["problem"],
        events=events,
    )
    session.add(row)
    return row


# --- video-events ----------------------------------------------------------------


async def mno_exists(session: AsyncSession, mno_id: UUID) -> bool:
    """Есть ли МНО с таким id в нашей БД (проверка п.3 Таблицы 3)."""
    stmt = select(Mno.id).where(Mno.id == mno_id)
    return (await session.execute(stmt)).first() is not None


async def save_video_event(session: AsyncSession, item: dict) -> UtkoVideoEvent:
    """Сохранить событие видеопотока; вернуть строку (id = videoEventUuid в ответе)."""
    row = UtkoVideoEvent(
        mno_id=item["mno_id"],
        external_event_id=item["external_event_id"],
        event_time=item["event_time"],
        photo_link=item["photo_link"],
        events=item["events"] if item["events"] else None,
    )
    session.add(row)
    await session.flush()  # получить сгенерированный id для ответа
    return row
