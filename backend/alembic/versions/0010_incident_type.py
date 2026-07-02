"""incidents: incident_type (код типа инцидента из справочника, nullable)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-02

incident_type хранит КОД типа инцидента (напр. «fire») из справочника
services/incident_types.py; русская подпись резолвится по коду на фронте.
Заполняется публичной формой волонтёра (обязательный дропдаун). Бэкфилла НЕТ —
у старых инцидентов типа не было → остаются NULL (Макс-бот тип тоже не проставляет).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("incident_type", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents", "incident_type")
