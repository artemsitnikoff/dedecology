"""incidents: comment (прочая не-адресная информация из текста обращения)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # comment: вся ПРОЧАЯ информация из свободного текста обращения, НЕ являющаяся
    # адресом («Радар №…», ФИО заявителя из текста, описание проблемы, заметки).
    # Раньше AI это выкидывал. Бэкфилла НЕТ — у старых инцидентов инфа уже срезана
    # прошлым reprocess и из полей не восстановима → остаются NULL.
    op.add_column(
        "incidents",
        sa.Column("comment", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents", "comment")
