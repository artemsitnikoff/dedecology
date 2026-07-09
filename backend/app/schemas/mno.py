"""Схемы МНО (места накопления отходов)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .base import ORMBase


class MnoListItem(ORMBase):
    """Строка реестра МНО. region_name резолвится из справочника регионов."""
    id: UUID
    reg: str
    name: str
    region_code: str
    region_name: str
    city: str
    address: str
    coords: str
    # Происхождение: 'fgis' (из ФГИС/по умолчанию) | 'volunteer' (добавлен волонтёром
    # на форме). Админка показывает бейдж «Добавлен волонтёром». Дефолт 'fgis' совпадает
    # с server_default колонки — _to_list_item всегда подставляет реальное m.source.
    source: str = "fgis"
    fgis_id: Optional[str] = None
    synced: bool
    sync_date: Optional[datetime] = None
    incidents: int
    # Момент создания записи МНО (фиксируется на бэке при вставке = Mno.created_at).
    # Отдаётся как `received_at` — мобильное приложение читает именно это имя; показывается
    # как «дата создания» в разделе «Новые МНО». Optional — старые ответы.
    received_at: Optional[datetime] = None


class MnoDetail(MnoListItem):
    """Карточка МНО: поля списка + комментарий и фото (только у волонтёрских МНО).

    comment/photo_urls есть лишь у МНО, добавленных волонтёром на публичной форме
    (POST /intake/mno). У синхронизированных из ФГИС / ручных МНО — comment=None,
    photo_urls=[] (список реестра остаётся лёгким — MnoListItem их не несёт).
    """
    comment: Optional[str] = None
    photo_urls: list[str] = []


class MnoCreate(BaseModel):
    """Создание МНО вручную. Обязательны только name + coords.

    synced=false, fgis_id=null, incidents=0 проставляются сервисом — НЕ из тела.
    """
    name: str = Field(min_length=1)
    coords: str = Field(min_length=1)
    reg: str = ""
    region_code: str = ""
    city: str = ""
    address: str = ""


class MnoVolunteerCreate(BaseModel):
    """Создание МНО волонтёром на ПУБЛИЧНОЙ форме (POST /intake/mno).

    Обязательны address + coords — но проверка НЕ через min_length (это дало бы 422),
    а в сервисе: пустые → ValidationError → 400 VALIDATION_ERROR (по контракту приёма).
    website — honeypot (у людей всегда пусто). name/region_code/city — необязательны.
    comment — необязательный комментарий волонтёра (сервис обрезает до 500). Фото приходят
    отдельными файлами в multipart-эндпоинте (НЕ в этой модели). source='volunteer',
    synced=false, fgis_id=null, reg='', incidents=0 проставляются сервисом — НЕ из тела.
    """
    address: str = ""
    coords: str = ""
    name: str = ""
    region_code: str = ""
    city: str = ""
    comment: str = ""
    website: str = ""  # honeypot — у людей всегда пусто


class MnoSyncResult(BaseModel):
    """Итог ЗАГЛУШКИ синхронизации с ФГИС: сколько помечено / всего МНО."""
    synced: int
    total: int


class MnoPoint(ORMBase):
    """Лёгкая точка МНО для карты: id + координаты «lat, lon» + название."""
    id: UUID
    coords: str
    name: str


class MnoPointsResponse(BaseModel):
    """Точки МНО для карты (отдельный лёгкий эндпоинт, без пагинации).

    total — всего МНО по текущему фильтру; points — первые не более лимита точек
    с непустыми координатами; capped=True — total превысил лимит и points обрезаны.
    """
    points: list[MnoPoint]
    total: int
    capped: bool


class MnoFormPoint(ORMBase):
    """Точка МНО для ПУБЛИЧНОЙ формы выбора площадки на карте.

    Помимо координат несёт реестровый № (reg), адрес, регион и город — клик по точке
    подставляет всё это в форму (регион+город+улица+координаты+рег-номер). name — подпись/поиск.
    """
    id: UUID
    coords: str
    reg: str
    address: str
    name: str
    region: str = ""  # имя субъекта РФ (из справочника Region по region_code) — для поля «Регион»
    city: str = ""    # город/н.п. МНО — для поля «Город»


class MnoFormPointsResponse(BaseModel):
    """Точки МНО в видимой области карты для публичной формы (bbox-кадр).

    total — число МНО в кадре; points — первые не более лимита; capped=True —
    total превысил лимит и points обрезаны (пусть пользователь приблизит карту).
    """
    points: list[MnoFormPoint]
    total: int
    capped: bool
