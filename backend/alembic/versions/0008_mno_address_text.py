"""mno.address → TEXT (адреса ФГИС бывают длиннее 500 символов — списки домов)

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-02

Без этого INSERT части МНО падал StringDataRightTruncationError и рушил транзакцию
региона (32 региона легли при прогоне «все регионы»). VARCHAR(500)→TEXT в PostgreSQL —
метаданные, без переписывания таблицы.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "mno",
        "address",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
        existing_server_default=sa.text("''"),
    )


def downgrade() -> None:
    # Обрезка до 500 при откате (длинные адреса усекутся) — иначе ALTER упадёт.
    op.execute("UPDATE mno SET address = left(address, 500)")
    op.alter_column(
        "mno",
        "address",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
        existing_server_default=sa.text("''"),
    )
