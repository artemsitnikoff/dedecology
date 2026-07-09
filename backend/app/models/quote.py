import uuid

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin


class Quote(Base, CreatedAtMixin):
    """Пул мотивирующих эко-строк для показа после приёма обращения.

    Статичный справочник: заполняется миграцией 0022 из services/quotes_data.py
    (курируемые реальные цитаты + оригинальные эко-строки). `nature_quote()` берёт
    случайную строку отсюда (ORDER BY random()) — вместо медленного claude CLI.
    Редактируется при желании прямо в БД.
    """

    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
