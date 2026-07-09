"""quotes: пул мотивирующих эко-строк + сид (~301) — замена claude CLI для цитат

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-09

Цитата после приёма обращения бралась через claude CLI (~15-20с на запрос — замер с
прода). Заменяем на СЛУЧАЙНУЮ строку из таблицы quotes. Таблица засевается здесь пулом
из services/quotes_data.py (курируемые реальные цитаты + оригинальные эко-строки, БЕЗ
приписывания авторам). quotes_data — чистый data-модуль (только список), импорт в
миграции безопасен. id/created_at — через server_default.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.services.quotes_data import QUOTES

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    quotes = op.create_table(
        "quotes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Сид пула: id/created_at — через server_default (не задаём).
    op.bulk_insert(quotes, [{"text": q} for q in QUOTES])


def downgrade() -> None:
    op.drop_table("quotes")
