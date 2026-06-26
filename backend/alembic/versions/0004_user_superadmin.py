"""users: is_superadmin (защищённый супер-админ вместо инвайт-флоу)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # is_superadmin: защищённый супер-админ — нельзя удалить, разжаловать
    # или сбросить ему пароль чужими руками (только сам через /profile/password).
    op.add_column(
        "users",
        sa.Column(
            "is_superadmin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Бэкфилл: помечаем самого СТАРОГО admin супер-админом (в проде это сидовый
    # pulse@reo.ru). Остальные admin остаются обычными.
    op.execute(
        "UPDATE users SET is_superadmin = true "
        "WHERE id = (SELECT id FROM users WHERE role = 'admin' "
        "ORDER BY created_at ASC LIMIT 1)"
    )


def downgrade() -> None:
    op.drop_column("users", "is_superadmin")
