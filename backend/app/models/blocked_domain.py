import uuid

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class BlockedEmailDomain(Base, TimestampMixin):
    """Справочник «Стоп-лист почтовых доменов» (редактируемый в админке).

    Домен хранится нормализованным (в нижнем регистре, напр. "gmail.com").
    Регистрация волонтёра с адресом на этом домене запрещается
    (services/volunteer.register проверяет is_email_blocked до создания записи).
    Список редактируется админом; сид иностранных бесплатных провайдеров —
    миграция 0024 (российские mail.ru/yandex.ru и т.п. НЕ блокируем).
    """

    __tablename__ = "blocked_email_domains"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Домен почты в нижнем регистре (напр. "gmail.com"). Уникален.
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
