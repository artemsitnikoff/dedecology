"""volunteers: убрать fio, добавить last_seen_at (последняя авторизация)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-02

У волонтёра больше нет поля «Заявитель» (fio) — регистрация только по email+паролю.
Вместо него — last_seen_at: момент последней авторизации волонтёра (успешный логин
и/или запрос по его JWT, с троттлингом). Nullable: у существующих записей неизвестно.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("volunteers", "fio")
    op.add_column(
        "volunteers",
        sa.Column(
            "last_seen_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("volunteers", "last_seen_at")
    op.add_column(
        "volunteers",
        sa.Column(
            "fio",
            sa.String(length=255),
            server_default=sa.text("''"),
            nullable=False,
        ),
    )
