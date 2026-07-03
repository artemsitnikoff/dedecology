"""incidents.mno_id: ссылка на выбранное МНО (UUID) + индекс

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-03

На публичной форме /form волонтёр выбирает МНО (место накопления отходов) на карте.
Раньше сохранялся только реестровый № (0014, incidents.mno_reg). Здесь добавляем
ССЫЛКУ на само МНО — incidents.mno_id (Mno.id). По ней считается живой счётчик
обращений у МНО и фильтруется список «инциденты этого МНО» (GET /incidents?mno_id=).
Nullable + БЕЗ жёсткого FK (как region_code у Mno) — свободная привязка: выбор МНО
необязателен (адрес можно ввести вручную), у Макс-бота и старых инцидентов его нет.
Индекс ix_incidents_mno_id — под COUNT/фильтр по mno_id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("mno_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_incidents_mno_id", "incidents", ["mno_id"])


def downgrade() -> None:
    op.drop_index("ix_incidents_mno_id", table_name="incidents")
    op.drop_column("incidents", "mno_id")
