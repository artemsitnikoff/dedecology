"""Справочник «Типы инцидентов»: CRUD над таблицей incident_types.

Источник правды в рантайме — БД (модуль-константа services/incident_types.py
остаётся ТОЛЬКО источником дефолтов для миграции 0011, из кода больше не читается).
Код типа (code) неизменяем после создания: на него слабой связью ссылаются
инциденты (Incident.incident_type), как region_code у МНО. Удаление типа НЕ трогает
инциденты — у них останется код, подпись просто перестанет резолвиться («—»).
Все функции async, session — первым параметром; flush() здесь, commit() — в роутере.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import ConflictError, NotFoundError
from ..models import IncidentType

_LABEL_MAX = 500
_CODE_MAX = 64


async def list_types(session: AsyncSession) -> list[IncidentType]:
    """Все типы инцидента, упорядоченные по sort_order, затем по code."""
    result = await session.execute(
        select(IncidentType).order_by(IncidentType.sort_order, IncidentType.code)
    )
    return list(result.scalars().all())


async def labels_map(session: AsyncSession) -> dict[str, str]:
    """code → label по всему справочнику из БД (для подписи типа в .xlsx-экспорте)."""
    result = await session.execute(select(IncidentType.code, IncidentType.label))
    return {code: label for code, label in result.all()}


async def code_exists(session: AsyncSession, code: str) -> bool:
    """True, если тип с таким кодом есть в справочнике (пустой код → False)."""
    code = (code or "").strip()
    if not code:
        return False
    result = await session.execute(
        select(IncidentType.id).where(IncidentType.code == code)
    )
    return result.scalar_one_or_none() is not None


async def get_type(session: AsyncSession, type_id) -> IncidentType:
    """Тип по id; отсутствует → NotFoundError (404)."""
    result = await session.execute(
        select(IncidentType).where(IncidentType.id == type_id)
    )
    incident_type = result.scalar_one_or_none()
    if incident_type is None:
        raise NotFoundError("Тип инцидента")
    return incident_type


async def _next_sort_order(session: AsyncSession) -> int:
    """Следующий порядок = max(sort_order)+1 (0 для пустого справочника)."""
    result = await session.execute(select(func.max(IncidentType.sort_order)))
    current = result.scalar_one_or_none()
    return current + 1 if current is not None else 0


def _gen_code() -> str:
    """Стабильный автокод: 'type_' + короткий hex uuid (напр. 'type_3f9a1c2b')."""
    return f"type_{uuid.uuid4().hex[:8]}"


async def create_type(
    session: AsyncSession,
    label: str,
    code: str | None = None,
    sort_order: int | None = None,
) -> IncidentType:
    """Создаёт тип инцидента.

    label обязателен (обрезается до 500). code: пуст → генерится стабильный автокод
    ('type_' + hex) с проверкой уникальности; задан → проверяем уникальность
    (дубликат → ConflictError 409). sort_order по умолчанию = max(sort_order)+1.
    """
    label = (label or "").strip()[:_LABEL_MAX]
    code = (code or "").strip()[:_CODE_MAX]

    if code:
        if await code_exists(session, code):
            raise ConflictError(f"Тип с кодом «{code}» уже существует")
    else:
        # Автокод: перегенерируем при (крайне маловероятной) коллизии.
        code = _gen_code()
        while await code_exists(session, code):
            code = _gen_code()

    if sort_order is None:
        sort_order = await _next_sort_order(session)

    incident_type = IncidentType(code=code, label=label, sort_order=sort_order)
    session.add(incident_type)
    await session.flush()
    return incident_type


async def update_type(
    session: AsyncSession,
    type_id,
    label: str | None = None,
    sort_order: int | None = None,
) -> IncidentType:
    """Правит label/sort_order. code НЕ меняем (на него ссылаются инциденты).
    Тип не найден → NotFoundError (404)."""
    incident_type = await get_type(session, type_id)
    if label is not None:
        incident_type.label = label.strip()[:_LABEL_MAX]
    if sort_order is not None:
        incident_type.sort_order = sort_order
    await session.flush()
    return incident_type


async def delete_type(session: AsyncSession, type_id) -> None:
    """Удаляет тип. Инциденты с этим кодом остаются (слабая связь → покажут «—»).
    Тип не найден → NotFoundError (404)."""
    incident_type = await get_type(session, type_id)
    await session.delete(incident_type)
    await session.flush()
