import uuid
from typing import Optional

from sqlalchemy import String, ForeignKey, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin


class AuditLog(Base, CreatedAtMixin):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    # {before: {...}, after: {...}}
    changes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    actor_type: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'human'")
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('human', 'system')",
            name="check_audit_actor_type",
        ),
    )

    actor_user: Mapped[Optional["User"]] = relationship("User")
