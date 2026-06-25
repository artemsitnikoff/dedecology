"""initial schema: users, incidents, audit_log

Revision ID: 0001
Revises:
Create Date: 2026-06-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgcrypto нужен для gen_random_uuid() в server_default UUID-первичных ключей.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --- users ---
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("fio", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=10), server_default=sa.text("'user'"), nullable=False),
        sa.Column("status", sa.String(length=10), server_default=sa.text("'active'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("locked_until", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'user')", name="check_user_role"),
        sa.CheckConstraint("status IN ('active', 'invited')", name="check_user_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # --- incidents ---
    op.create_table(
        "incidents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=12), server_default=sa.text("'new'"), nullable=False),
        sa.Column("fio", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("region", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("city", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("street", sa.String(length=500), server_default=sa.text("''"), nullable=False),
        sa.Column("coords", sa.String(length=64), server_default=sa.text("''"), nullable=False),
        sa.Column("photo_time", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("photos", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("photo_urls", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("msg", sa.String(length=120), nullable=True),
        sa.Column("bins", sa.Boolean(), nullable=True),
        sa.Column("received_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source IN ('max', 'form')", name="check_incident_source"),
        sa.CheckConstraint("status IN ('new', 'found', 'none', 'exported')", name="check_incident_status"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("actor_type", sa.String(length=10), server_default=sa.text("'human'"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("actor_type IN ('human', 'system')", name="check_audit_actor_type"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("incidents")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
