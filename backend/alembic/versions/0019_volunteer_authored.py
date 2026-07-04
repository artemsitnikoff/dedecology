"""incidents.volunteer_id + mno.volunteer_id: авторство волонтёра (UUID) + индексы

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-04

Мобильному приложению нужен таб «Отчёты»: волонтёр видит СВОИ созданные отчёты
(инциденты, со статусом) и СВОИ добавленные МНО. При создании из приложения авторство
застолбляется опциональным volunteer-токеном на публичных POST /intake/form и
POST /intake/mno. Для этого добавляем МЯГКУЮ привязку автора (как incidents.mno_id,
миграция 0016) — nullable UUID + индекс, БЕЗ жёсткого FK:
  - incidents.volunteer_id — кто создал отчёт (GET /volunteer/reports фильтрует «мои»);
  - mno.volunteer_id — кто добавил МНО (GET /volunteer/mno фильтрует «мои»).
NULL — аноним/веб-форма/Макс/старые записи (историю задним числом не привязываем).
Индексы ix_incidents_volunteer_id / ix_mno_volunteer_id — под фильтр «мои» по volunteer_id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("volunteer_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_incidents_volunteer_id", "incidents", ["volunteer_id"])
    op.add_column(
        "mno",
        sa.Column("volunteer_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_mno_volunteer_id", "mno", ["volunteer_id"])


def downgrade() -> None:
    op.drop_index("ix_mno_volunteer_id", table_name="mno")
    op.drop_column("mno", "volunteer_id")
    op.drop_index("ix_incidents_volunteer_id", table_name="incidents")
    op.drop_column("incidents", "volunteer_id")
