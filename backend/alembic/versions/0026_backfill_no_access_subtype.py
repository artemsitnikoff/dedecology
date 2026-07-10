"""backfill: старым инцидентам типа no_access → подтип 'other_reason' («Иная причина»)

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-11

Подтип инцидента (миграция 0025) появился позже — у ранее принятых обращений типа
'no_access' («Отсутствует доступ к МНО») подтип пуст, из-за чего в УТКО-выгрузке
колонка «Подтип инцидента» пустая. Проставляем им дефолтный подтип 'other_reason'
(«Иная причина») — по требованию, чтобы в выгрузке было значение. Трогаем ТОЛЬКО
строки с типом no_access и пустым подтипом (идемпотентно; новые обращения уже
проставляют подтип на приёме). downgrade — обратно в NULL те же строки.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE incidents
        SET incident_subtype = 'other_reason'
        WHERE incident_type = 'no_access'
          AND (incident_subtype IS NULL OR incident_subtype = '')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE incidents
        SET incident_subtype = NULL
        WHERE incident_type = 'no_access'
          AND incident_subtype = 'other_reason'
        """
    )
