"""mno: is_published (волонтёрское МНО опубликовано модератором, bool NOT NULL)

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-19

is_published — флаг публикации волонтёрского МНО (source='volunteer') администратором.
По умолчанию false: добавленное волонтёром МНО скрыто из общих списков/карт, пока
админ не одобрит его (POST /mno/{id}/approve → is_published=true). У ФГИС/ручных МНО
(source != 'volunteer') флаг на видимость не влияет — они видны и так. server_default
false бэкфиллит существующие строки (видимость ФГИС/ручных не меняется).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mno",
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("mno", "is_published")
