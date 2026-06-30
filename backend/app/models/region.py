import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Integer, text
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Region(Base, TimestampMixin):
    """Субъект РФ (справочник «Регионы»).

    code = код субъекта = regionId в ФГИС (строка, напр. "63"/"77"/"16"). Уникален.
    PK — uuid (как у остальных таблиц), но связь с МНО идёт по code (строке).
    """

    __tablename__ = "regions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Код субъекта РФ = regionId ФГИС ("63", "77", …). Уникален → ключ связи с МНО.
    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # id федерального округа (нумерация ФГИС 1..8 — см. services/federal_districts.py)
    fed: Mapped[int] = mapped_column(Integer, nullable=False)
    # Региональные операторы по ТКО — список строк (несколько на регион)
    operators: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # Последняя синхронизация справочника (ЗАГЛУШКА ФГИС). NULL — ещё не синхронизирован.
    last_sync: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
