"""regions + mno (МНО и Регионы): справочники без бэкфилла

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- regions (субъекты РФ; code = regionId ФГИС, уникален) ---
    op.create_table(
        "regions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("fed", sa.Integer(), nullable=False),
        sa.Column(
            "operators",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_sync", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_regions_code"),
    )

    # --- mno (места накопления отходов; связь с регионом по region_code строкой) ---
    op.create_table(
        "mno",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("reg", sa.String(length=64), server_default=sa.text("''"), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("region_code", sa.String(length=8), server_default=sa.text("''"), nullable=False),
        sa.Column("city", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("address", sa.String(length=500), server_default=sa.text("''"), nullable=False),
        sa.Column("coords", sa.String(length=64), server_default=sa.text("''"), nullable=False),
        sa.Column("fgis_id", sa.String(length=64), nullable=True),
        sa.Column("synced", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sync_date", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("incidents", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mno_region_code", "mno", ["region_code"])
    op.create_index("ix_mno_synced", "mno", ["synced"])


def downgrade() -> None:
    op.drop_index("ix_mno_synced", table_name="mno")
    op.drop_index("ix_mno_region_code", table_name="mno")
    op.drop_table("mno")
    op.drop_table("regions")
