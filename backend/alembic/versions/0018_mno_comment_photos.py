"""mno.comment + mno.photo_urls: комментарий и фото волонтёрского МНО

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-04

На публичной форме (POST /intake/mno) волонтёр может добавить к новому МНО
комментарий (≤500 символов) и фотографии. У синхронизированных из ФГИС и ручных
МНО этих данных нет:
  - comment — TEXT, NULLABLE (у ФГИС/ручных МНО остаётся NULL);
  - photo_urls — JSONB, NOT NULL, server_default '[]'::jsonb (список URL фото);
    server_default бэкфиллит все существующие строки пустым списком фото.
Зеркалит механизм фото инцидентов (incidents.photo_urls, миграция 0001).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mno",
        sa.Column("comment", sa.Text(), nullable=True),
    )
    op.add_column(
        "mno",
        sa.Column(
            "photo_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("mno", "photo_urls")
    op.drop_column("mno", "comment")
