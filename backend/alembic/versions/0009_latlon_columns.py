"""числовые lat/lon для mno и incidents + индекс (bbox-догрузка точек карты)

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-02

coords хранится текстом «lat, lon» — для быстрого bbox-фильтра на сотнях тысяч строк
заводим числовые колонки lat/lon + составной индекс. Бэкфилл — ТОЛЬКО из валидных
«lat, lon» (regex-гард, иначе cast упал бы на мусорных/пустых coords). Невалидные/пустые
coords → lat/lon остаются NULL (такие точки на карту не идут — это ожидаемо).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mno", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("mno", sa.Column("lon", sa.Float(), nullable=True))
    op.add_column("incidents", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("incidents", sa.Column("lon", sa.Float(), nullable=True))

    # Бэкфилл из coords ТОЛЬКО для строк, где coords — валидная пара «lat, lon»
    # (regex-гард в WHERE защищает ::double precision от падения на мусоре).
    op.execute(
        r"UPDATE mno SET lat = split_part(coords,',',1)::double precision, "
        r"lon = trim(split_part(coords,',',2))::double precision "
        r"WHERE coords ~ '^\s*-?[0-9]+(\.[0-9]+)?\s*,\s*-?[0-9]+(\.[0-9]+)?\s*$'"
    )
    op.execute(
        r"UPDATE incidents SET lat = split_part(coords,',',1)::double precision, "
        r"lon = trim(split_part(coords,',',2))::double precision "
        r"WHERE coords ~ '^\s*-?[0-9]+(\.[0-9]+)?\s*,\s*-?[0-9]+(\.[0-9]+)?\s*$'"
    )

    op.create_index("ix_mno_lat_lon", "mno", ["lat", "lon"])
    op.create_index("ix_incidents_lat_lon", "incidents", ["lat", "lon"])


def downgrade() -> None:
    op.drop_index("ix_incidents_lat_lon", table_name="incidents")
    op.drop_index("ix_mno_lat_lon", table_name="mno")
    op.drop_column("incidents", "lon")
    op.drop_column("incidents", "lat")
    op.drop_column("mno", "lon")
    op.drop_column("mno", "lat")
