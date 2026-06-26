"""incidents: notified_at + quote (групповые уведомления Макс)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # notified_at: момент успешной отправки в группу Макс (NULL → ещё не отправлено).
    op.add_column(
        "incidents",
        sa.Column("notified_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    # quote: сгенерированная цитата о природе, сохранённая для повторного показа.
    op.add_column(
        "incidents",
        sa.Column("quote", sa.Text(), nullable=True),
    )
    # Бэкфилл: все СУЩЕСТВУЮЩИЕ инциденты считаем уже уведомлёнными, чтобы при первом
    # запуске notify-цикл не засыпал группу историей (демо + тестовые). В группу пойдут
    # только НОВЫЕ обращения, созданные после миграции (у них notified_at = NULL).
    op.execute("UPDATE incidents SET notified_at = now() WHERE notified_at IS NULL")


def downgrade() -> None:
    op.drop_column("incidents", "quote")
    op.drop_column("incidents", "notified_at")
