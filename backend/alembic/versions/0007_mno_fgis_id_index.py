"""mno.fgis_id index (upsert по fgis_id при синхронизации с ФГИС)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-01

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # UPSERT синхронизации МНО ищет строку по fgis_id — индекс убирает seq-scan.
    op.create_index("ix_mno_fgis_id", "mno", ["fgis_id"])


def downgrade() -> None:
    op.drop_index("ix_mno_fgis_id", table_name="mno")
