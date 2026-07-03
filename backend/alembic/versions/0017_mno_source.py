"""mno.source: происхождение МНО ('fgis' | 'volunteer')

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-03

На публичной форме волонтёр может ДОБАВИТЬ новое МНО, если нужного нет на карте
(POST /intake/mno). Такой МНО помечается source='volunteer' — в отличие от 'fgis'
(синхронизированные из ФГИС / по умолчанию), чтобы эколог в админке видел бейдж
«Добавлен волонтёром» и мог проверить точку. NOT NULL + server_default 'fgis':
все существующие МНО (из ФГИС/ручные/сид) бэкфиллятся как 'fgis'.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mno",
        sa.Column(
            "source",
            sa.String(length=16),
            nullable=False,
            server_default="fgis",
        ),
    )


def downgrade() -> None:
    op.drop_column("mno", "source")
