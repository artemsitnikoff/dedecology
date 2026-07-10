"""blocked_email_domains: стоп-лист почтовых доменов + сид иностранных провайдеров

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-10

Редактируемый в админке справочник доменов, с которых регистрация волонтёра
запрещена (services/volunteer.register проверяет is_email_blocked). Домен хранится
нормализованным (нижний регистр, уникален). Сид — иностранные бесплатные почтовые
провайдеры (снимок здесь, чтобы миграция была самодостаточной); российские
mail.ru/yandex.ru/bk.ru/list.ru/inbox.ru/rambler.ru НЕ блокируем. id проставляет БД
(gen_random_uuid()), created_at/updated_at — server_default now().
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Снимок сида: иностранные бесплатные почтовые провайдеры (нормализованы в lowercase).
_DEFAULT_DOMAINS: list[str] = [
    "gmail.com",
    "googlemail.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "yahoo.com",
    "ymail.com",
    "rocketmail.com",
    "aol.com",
    "gmx.com",
    "gmx.net",
    "proton.me",
    "protonmail.com",
    "pm.me",
    "zoho.com",
    "tutanota.com",
    "tuta.io",
    "fastmail.com",
    "mail.com",
    "web.de",
    "yahoo.co.uk",
]


def upgrade() -> None:
    blocked_email_domains = op.create_table(
        "blocked_email_domains",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(length=255), nullable=False),
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
        sa.UniqueConstraint("domain", name="uq_blocked_email_domains_domain"),
    )

    # Сид: id/created_at/updated_at — через server_default (не задаём).
    op.bulk_insert(
        blocked_email_domains,
        [{"domain": d} for d in _DEFAULT_DOMAINS],
    )


def downgrade() -> None:
    op.drop_table("blocked_email_domains")
