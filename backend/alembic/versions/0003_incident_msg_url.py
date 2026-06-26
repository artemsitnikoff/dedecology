"""incidents: msg_url (готовый https-URL сообщения Макс)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # msg_url: готовый полный https-URL сообщения Макс (Message.url). Старые
    # инциденты бэкфилла НЕ получают — прежние ссылки https://max.ru/m/{mid} были
    # битыми, поэтому остаются NULL → ссылка просто не показывается.
    op.add_column(
        "incidents",
        sa.Column("msg_url", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents", "msg_url")
