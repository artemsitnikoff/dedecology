"""Серверный экспорт реестра МНО в .xlsx (openpyxl) — по образцу services/export.py."""

from io import BytesIO
from typing import Iterable

from openpyxl import Workbook

from ..schemas.mno import MnoListItem

_HEADERS = [
    "Реестровый №",
    "Наименование",
    "Код региона",
    "Регион",
    "Город / н.п.",
    "Адрес",
    "Координаты",
    "ID в ФГИС",
    "Синхронизация",
    "Дата синхронизации",
    "Обращений по МНО",
]


def _sync_date(item: MnoListItem) -> str:
    if item.sync_date is None:
        return ""
    return item.sync_date.strftime("%d.%m.%Y")


def _row(item: MnoListItem) -> list:
    return [
        item.reg,
        item.name,
        item.region_code,
        item.region_name,
        item.city,
        item.address,
        item.coords,
        item.fgis_id or "",
        "ФГИС" if item.synced else "Вручную",
        _sync_date(item),
        item.incidents,
    ]


def build_mno_xlsx(rows: Iterable[MnoListItem]) -> bytes:
    """Строит .xlsx (bytes) реестра МНО. Первая строка — заголовки."""
    wb = Workbook()
    ws = wb.active
    ws.title = "МНО"
    ws.append(_HEADERS)
    for item in rows:
        ws.append(_row(item))
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
