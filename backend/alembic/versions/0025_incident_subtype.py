"""incidents: incident_subtype (код подтипа инцидента, nullable)

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-11

incident_subtype хранит КОД подтипа инцидента ('blocked_by_car' | 'other_reason')
из фиксированного справочника services/incident_subtypes.py. Подтип есть ТОЛЬКО у
типа с кодом 'no_access' («Отсутствует доступ к МНО»); для остальных типов — NULL.
Бэкфилла НЕТ — у старых инцидентов подтипа не было → остаются NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("incident_subtype", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents", "incident_subtype")
