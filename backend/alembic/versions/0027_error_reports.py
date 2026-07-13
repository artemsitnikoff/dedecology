"""error_reports: журнал технических ошибок мобильного приложения

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-13

Каждая строка — одна техническая ошибка, присланная приложением при сбое
(POST /intake/error-report). code — уникальный человекочитаемый код ("ERR-XXXXXXXX"),
technical — произвольный JSON (stacktrace/запрос/устройство), emailed/email_error —
честный исход отправки письма в техподдержку.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "error_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("error_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("app_version", sa.String(length=64), nullable=True),
        sa.Column("user_action", sa.Text(), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=True),
        sa.Column(
            "technical",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        sa.Column("occurred_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("volunteer_email", sa.String(length=255), nullable=True),
        sa.Column("emailed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("email_error", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_error_reports_code"),
    )


def downgrade() -> None:
    op.drop_table("error_reports")
