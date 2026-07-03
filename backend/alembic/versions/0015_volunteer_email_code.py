"""volunteers: подтверждение почты 4-значным кодом (OTP) вместо verify-ссылки

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-03

Подтверждение адреса почты волонтёра переезжает с длинного JWT-verify-токена на
короткий 4-значный код, высылаемый письмом. В таблицу volunteers добавляем:
  - email_code — текущий код подтверждения (напр. "0472"), nullable;
  - email_code_expires_at — срок действия кода (истёк → нужен новый), nullable;
  - email_code_sent_at — момент последней отправки (кулдаун повторной отправки), nullable;
  - email_code_attempts — счётчик неверных попыток (антибрутфорс), NOT NULL default 0.
Пароль-reset (по JWT-токену) НЕ меняется — этих колонок он не касается.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "volunteers",
        sa.Column("email_code", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "volunteers",
        sa.Column(
            "email_code_expires_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "volunteers",
        sa.Column(
            "email_code_sent_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "volunteers",
        sa.Column(
            "email_code_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("volunteers", "email_code_attempts")
    op.drop_column("volunteers", "email_code_sent_at")
    op.drop_column("volunteers", "email_code_expires_at")
    op.drop_column("volunteers", "email_code")
