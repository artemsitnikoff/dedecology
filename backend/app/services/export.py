"""Серверный экспорт инцидентов в .xlsx (openpyxl). 13 колонок в порядке ТЗ §7."""

from io import BytesIO
from typing import Iterable

from openpyxl import Workbook

from ..models import Incident

# Лейблы — зеркало data.js STATUS/SOURCE
_STATUS_LABELS = {
    "new": "Новый",
    "found": "Инцидент обнаружен",
    "none": "Нет инцидента",
    "exported": "Выгружен",
}
_SOURCE_LABELS = {
    "max": "Макс",
    "form": "Яндекс форма",
}

# Заголовки в точном порядке (ТЗ §7 / прототип toCsv)
_HEADERS = [
    "ФИО",
    "Источник",
    "Статус",
    "Регион",
    "Город / н.п.",
    "Адрес (улица)",
    "Полный адрес",
    "Координаты",
    "Дата фотофиксации",
    "Время фотофиксации",
    "Кол-во фото",
    "Ссылка на сообщение",
    "Поступило",
]


def _full_addr(inc: Incident) -> str:
    return f"{inc.region}, {inc.city}, {inc.street}"


def _photo_date(inc: Incident) -> str:
    """ДД.ММ.ГГГГ или '' если фотофиксации нет."""
    if inc.photo_time is None:
        return ""
    return inc.photo_time.strftime("%d.%m.%Y")


def _photo_time(inc: Incident) -> str:
    """ЧЧ:ММ или '' если фотофиксации нет."""
    if inc.photo_time is None:
        return ""
    return inc.photo_time.strftime("%H:%M")


def _message_link(inc: Incident) -> str:
    """Готовый https-URL сообщения (msg_url) как есть; иначе '' (без фолбэка на mid)."""
    return inc.msg_url or ""


def _received(inc: Incident) -> str:
    if inc.received_at is None:
        return ""
    return inc.received_at.strftime("%Y-%m-%d %H:%M")


def _row(inc: Incident) -> list:
    return [
        inc.fio,
        _SOURCE_LABELS.get(inc.source, inc.source),
        _STATUS_LABELS.get(inc.status, inc.status),
        inc.region,
        inc.city,
        inc.street,
        _full_addr(inc),
        inc.coords,
        _photo_date(inc),
        _photo_time(inc),
        inc.photos,
        _message_link(inc),
        _received(inc),
    ]


def build_xlsx(rows: Iterable[Incident]) -> bytes:
    """Строит .xlsx (bytes) из инцидентов. 13 колонок, первая строка — заголовки."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Инциденты"

    ws.append(_HEADERS)
    for inc in rows:
        ws.append(_row(inc))

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
