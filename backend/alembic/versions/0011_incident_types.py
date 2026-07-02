"""incident_types: редактируемый справочник «Типы инцидентов» + сид 10 дефолтов

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-02

Выносит хардкод-справочник services/incident_types.py в редактируемую таблицу
incident_types (источник правды). Код типа (code) уникален и неизменяем — на него
слабой связью ссылаются инциденты (Incident.incident_type). Сид — 10 дефолтов из
services/incident_types.py (значения продублированы здесь, чтобы миграция была
самодостаточным снимком и не зависела от будущих правок кода). id проставляет БД
(gen_random_uuid()), created_at/updated_at — server_default now().
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 10 дефолтов (снимок services/incident_types.py на момент миграции).
_DEFAULT_TYPES: list[dict] = [
    {"code": "no_access", "label": "Отсутствует доступ к МНО"},
    {"code": "blocked_access", "label": "Проезд заблокирован автомобилем"},
    {"code": "no_container", "label": "Контейнер отсутствует"},
    {"code": "fire", "label": "Возгорание в контейнере"},
    {
        "code": "non_tko_in_container",
        "label": "В контейнере находятся отходы, не относящиеся к ТКО",
    },
    {"code": "damaged_container", "label": "Контейнер поврежден"},
    {"code": "waste_nearby", "label": "Наличие отходов рядом с МНО"},
    {
        "code": "non_tko_on_site",
        "label": "На контейнерной площадке вне контейнеров зафиксированы отходы, "
        "не относящиеся к ТКО",
    },
    {"code": "overflow", "label": "Зафиксировано переполнение контейнеров"},
    {"code": "other", "label": "Иное"},
]


def upgrade() -> None:
    incident_types = op.create_table(
        "incident_types",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_incident_types_code"),
    )

    # Сид 10 дефолтов: id/created_at/updated_at — через server_default (не задаём).
    op.bulk_insert(
        incident_types,
        [
            {"code": t["code"], "label": t["label"], "sort_order": i}
            for i, t in enumerate(_DEFAULT_TYPES)
        ],
    )


def downgrade() -> None:
    op.drop_table("incident_types")
