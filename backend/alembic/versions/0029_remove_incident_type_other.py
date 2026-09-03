"""incident_types: убрать тип «Иное» (code='other') из справочника, сохранив историю

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-03

Рантайм-справочник типов инцидента — БД-таблица incident_types (её читают эндпоинт
/intake/incident-types, публичная форма, maxbot, telegrambot). Убираем из НЕЁ строку
«Иное» (code='other') — в новых обращениях этот тип больше выбрать нельзя.

Историю НЕ трогаем: у существующих инцидентов остаётся код 'other', а его подпись
«Иное» резолвится статик-фолбэком services/incident_types.INCIDENT_TYPES (utko_export.
_type_label / export.py падают на _static_type_label, когда кода нет в БД-labels).
Бэкфилла инцидентов нет.

⚠️ Подтип «Иная причина» (other_reason) у типа «Отсутствует доступ к МНО» — ОТДЕЛЬНАЯ
сущность (incident_subtypes), эта миграция его не касается.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Убираем тип «Иное» из редактируемого справочника (рантайм-выбор). Инциденты с
    # уже проставленным кодом 'other' не трогаем — подпись даёт статик-фолбэк.
    op.execute("DELETE FROM incident_types WHERE code = 'other'")


def downgrade() -> None:
    # Возвращаем строку «Иное». id/created_at/updated_at — через server_default
    # (gen_random_uuid()/now()); sort_order=9 — как в сиде 0011 (10-й, последний тип).
    op.execute(
        "INSERT INTO incident_types (code, label, sort_order) "
        "VALUES ('other', 'Иное', 9) "
        "ON CONFLICT (code) DO NOTHING"
    )
