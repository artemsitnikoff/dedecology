import uuid
from typing import Optional

from sqlalchemy import String, Integer, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin


class Report(Base, CreatedAtMixin):
    """Отчёт — сформированная Excel-выгрузка обращений (история + повторное скачивание).

    Файл на диске = {STORAGE_DIR}/reports/{id}.xlsx — путь детерминирован по id, поэтому
    отдельной колонки пути НЕТ. filename — человекочитаемое имя для Content-Disposition.
    Генерация синхронная (в запросе, без arq): сервис пишет файл на диск и строку сюда.
    """

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Тип отчёта — пока единственный 'incidents' (выгрузка обращений).
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'incidents'")
    )
    # Человекочитаемое имя файла для скачивания (Content-Disposition).
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Число строк в выгрузке (обращений).
    row_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    # Размер файла на диске в байтах (снимок на момент формирования).
    size_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    # Кто сформировал (FK users, SET NULL при удалении пользователя).
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Снимок ФИО автора — переживает удаление пользователя (created_by_id → NULL).
    created_by_fio: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("''")
    )
    # created_at — из CreatedAtMixin.
