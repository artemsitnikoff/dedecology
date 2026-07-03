"""incidents.mno_reg: рег-номер выбранного на карте формы МНО

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-03

На публичной форме /form волонтёр может выбрать МНО (место накопления отходов) на
карте — сохраняем его реестровый № (Mno.reg) в incidents.mno_reg. Nullable: выбор
МНО необязателен (адрес можно ввести вручную), у Макс-бота и старых инцидентов его нет.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("mno_reg", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents", "mno_reg")
