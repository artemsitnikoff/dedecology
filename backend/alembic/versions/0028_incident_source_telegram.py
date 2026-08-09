"""incidents.source: разрешить 'telegram' (обращения из Telegram-бота)

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-09

Telegram-бот шлёт обращения тем же приёмом, что Макс-бот (POST /intake/max +
/intake/max/finalize), но помечает их отдельным источником source='telegram'
(видно в админке/фильтрах/выгрузке отдельно от Max). Расширяем CHECK-констрейнт
incidents.source с ('max','form','app') до ('max','form','app','telegram').
Колонка incidents.source — String(8); «telegram» = 8 символов, влезает.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("check_incident_source", "incidents", type_="check")
    op.create_check_constraint(
        "check_incident_source",
        "incidents",
        "source IN ('max', 'form', 'app', 'telegram')",
    )


def downgrade() -> None:
    op.drop_constraint("check_incident_source", "incidents", type_="check")
    op.create_check_constraint(
        "check_incident_source", "incidents", "source IN ('max', 'form', 'app')"
    )
