"""Запись действий в audit_log (единый хелпер, single-tenant — без мультиарендности)."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog


async def audit(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    before: dict | None = None,
    after: dict | None = None,
    actor_user_id: UUID | None,  # None — для системных действий (actor_type='system')
    actor_type: str = "human",
) -> AuditLog:
    """Создаёт запись в audit_log. flush(), но НЕ commit — коммитит роутер."""
    changes: dict = {}
    if before is not None:
        changes["before"] = before
    if after is not None:
        changes["after"] = after

    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes or None,
        actor_type=actor_type,
        actor_user_id=actor_user_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(entry)
    await session.flush()
    return entry
