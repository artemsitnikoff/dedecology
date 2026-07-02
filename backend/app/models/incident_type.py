import uuid

from sqlalchemy import Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class IncidentType(Base, TimestampMixin):
    """Справочник «Типы инцидентов» (редактируемый в админке).

    Источник правды — эта таблица (заполняется миграцией 0011 дефолтами из
    services/incident_types.py). В инциденте хранится КОД типа (Incident.incident_type,
    строка) — связь слабая (как region_code): удаление типа НЕ трогает инциденты
    (у них останется код, подпись просто не резолвится → «—»). Поэтому code
    неизменяем после создания; правим только label/sort_order.
    """

    __tablename__ = "incident_types"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Код типа (напр. «fire»). Уникален; неизменяем — на него ссылаются инциденты.
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # Русская подпись типа (показывается в дропдауне формы / карточке / фильтре).
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    # Порядок вывода в справочнике/дропдауне (по возрастанию, затем по code).
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
