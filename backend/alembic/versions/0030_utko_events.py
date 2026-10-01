"""utko_* : таблицы ядра УТКО-совместимого API (приём данных посещения МНО)

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-01

Три таблицы интеграции с контрактом ФГИС УТКО (изолированы префиксом utko_):
  • utko_truck_visit_event   — события посещения МНО мусоровозом (выдаются /query);
  • utko_truck_visit_confirm — подтверждения опустошения (приём /confirm);
  • utko_video_event         — события обработки видеопотока (приём /video-events).

UUID PK gen_random_uuid() (расширение pgcrypto уже включено миграцией 0001),
TIMESTAMP(tz)=UTC. JSONB для массивов нарушений events. Жёстких FK нет сознательно:
приём данных интеграции не должен падать каскадом при рассинхроне с доменными таблицами.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "utko_truck_visit_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("mno_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_time", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_empty", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("photo_link_before", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("photo_link_after", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "create_date",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_utko_truck_visit_event_create_date",
        "utko_truck_visit_event",
        ["create_date"],
    )

    op.create_table(
        "utko_truck_visit_confirm",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_empty_confirmed", sa.Boolean(), nullable=False),
        sa.Column("problem", sa.Text(), nullable=True),
        sa.Column("events", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "create_date",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_utko_truck_visit_confirm_event_id",
        "utko_truck_visit_confirm",
        ["event_id"],
    )

    op.create_table(
        "utko_video_event",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("mno_id", postgresql.UUID(as_uuid=True), nullable=False),
        # externalEventId — в доке тип «uuid», но пример ответа echo-ит произвольную строку
        # «123» (таблица ответа — «строка»); храним как TEXT и возвращаем verbatim.
        sa.Column("external_event_id", sa.Text(), nullable=True),
        sa.Column("event_time", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("photo_link", sa.Text(), nullable=True),
        sa.Column("events", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "create_date",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("utko_video_event")
    op.drop_index(
        "ix_utko_truck_visit_confirm_event_id", table_name="utko_truck_visit_confirm"
    )
    op.drop_table("utko_truck_visit_confirm")
    op.drop_index(
        "ix_utko_truck_visit_event_create_date", table_name="utko_truck_visit_event"
    )
    op.drop_table("utko_truck_visit_event")
