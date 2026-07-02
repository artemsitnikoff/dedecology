"""volunteers: отдельная таблица волонтёров мобильного приложения

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-02

Создаёт таблицу volunteers — учётки волонтёров мобильного приложения, ОТДЕЛЬНЫЕ от
пользователей админки (users). Своя аутентификация (JWT typ="volunteer"), подтверждение
почты и блокировка админом. id проставляет БД (gen_random_uuid()), created_at/updated_at —
server_default now(). email — уникальный индекс ix_volunteers_email.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "volunteers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("fio", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Уникальный индекс на email (совпадает с моделью: unique=True + index=True).
    op.create_index(
        "ix_volunteers_email", "volunteers", ["email"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_volunteers_email", table_name="volunteers")
    op.drop_table("volunteers")
