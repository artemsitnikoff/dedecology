"""smtp_settings: настройки почтового сервера (SMTP) — единственная строка на арендатора

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-08

Редактируемая из админки конфигурация SMTP + тестовая отправка. Single-tenant:
в таблице живёт не более одной строки (get-or-create в сервисе). Пароль хранится
ТОЛЬКО зашифрованным (Fernet) в password_enc и наружу не отдаётся. status='connected'
выставляется лишь после успешной тестовой отправки; last_test_* фиксируют её исход.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "smtp_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("host", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("port", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("encryption", sa.String(length=8), server_default=sa.text("'ssl'"), nullable=False),
        sa.Column("username", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("password_enc", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("from_email", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("from_name", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'disconnected'"), nullable=False),
        sa.Column("last_test_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("smtp_settings")
