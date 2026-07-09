"""incidents.source: разрешить 'app' (мобильное приложение волонтёра)

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-09

Мобильное приложение волонтёра шлёт обращения в POST /intake/form с volunteer-токеном
(в отличие от анонимной веб-формы). Различаем источник: с токеном → source='app'.
Расширяем CHECK-констрейнт incidents.source с ('max','form') до ('max','form','app').
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("check_incident_source", "incidents", type_="check")
    op.create_check_constraint(
        "check_incident_source", "incidents", "source IN ('max', 'form', 'app')"
    )


def downgrade() -> None:
    op.drop_constraint("check_incident_source", "incidents", type_="check")
    op.create_check_constraint(
        "check_incident_source", "incidents", "source IN ('max', 'form')"
    )
