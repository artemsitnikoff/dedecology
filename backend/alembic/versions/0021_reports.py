"""reports: история сформированных Excel-выгрузок обращений (файл на диске + повторное скачивание)

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-09

Каждая строка — один сформированный отчёт (kind='incidents'). Сам файл лежит на диске
по детерминированному пути {STORAGE_DIR}/reports/{id}.xlsx (колонки пути НЕТ). filename —
человекочитаемое имя для скачивания; created_by_fio — снимок ФИО автора (переживает
удаление пользователя, при котором created_by_id → NULL).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=16), server_default=sa.text("'incidents'"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("row_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("size_bytes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_fio", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )


def downgrade() -> None:
    op.drop_table("reports")
