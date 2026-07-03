import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Float, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Mno(Base, TimestampMixin):
    """МНО — место накопления отходов (контейнерная площадка, «слой 5» ФГИС).

    region_code — строковый код субъекта (→ Region.code), без жёсткого FK: МНО можно
    завести вручную с любым кодом, привязка к справочнику — по значению (см. сервис).
    """

    __tablename__ = "mno"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Реестровый № в ФГИС, напр. "63-04-001162" (для ручных МНО может быть пустым)
    reg: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("''"))
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    # Код субъекта РФ (→ Region.code). Индексирован для фильтра по региону.
    region_code: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default=text("''"), index=True
    )
    city: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("''"))
    # TEXT (не String(500)): ФГИС кладёт в адрес длинные списки домов (>500 символов),
    # иначе INSERT падает StringDataRightTruncationError и рушит транзакцию региона (см. 0008).
    address: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    # "широта, долгота" текстом (как у инцидента)
    coords: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("''"))
    # Числовые координаты (миграция 0009): дублируют coords для быстрого bbox-фильтра
    # карты по индексу ix_mno_lat_lon. NULL — coords пусты/невалидны (точка не на карте).
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Происхождение МНО (миграция 0017): 'fgis' — синхронизировано из ФГИС / по
    # умолчанию (ручное/сидовое); 'volunteer' — добавлено волонтёром на публичной
    # форме (POST /intake/mno). Админка показывает бейдж «Добавлен волонтёром».
    # server_default 'fgis' → все существующие строки бэкфиллятся как 'fgis'.
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'fgis'")
    )
    # ID в ФГИС. NULL — МНО заведено вручную и в ФГИС ещё не выгружено.
    fgis_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Синхронизировано с ФГИС (ЗАГЛУШКА — реальной интеграции нет, см. сервис)
    synced: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), index=True
    )
    sync_date: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # Число обращений по МНО — СИДОВОЕ/хранимое значение (точная привязка по координатам —
    # прод-TODO; здесь НЕ вычисляется на лету, чтобы не выдумывать несуществующую логику).
    incidents: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
