"""Серверный экспорт инцидентов в .xlsx (openpyxl). 17 колонок: порядок ТЗ §7 + комментарий +
3 столбца «Фото 1/2/3» (формула =IMAGE(url) — картинка по URL прямо в ячейке, Excel 365/Online)."""

from io import BytesIO
from typing import Iterable

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

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
    "Заявитель",
    "Источник",
    "Статус",
    "Регион",
    "Город / н.п.",
    "Адрес (улица)",
    "Полный адрес",
    "Координаты",
    "Комментарий",
    "Дата фотофиксации",
    "Время фотофиксации",
    "Кол-во фото",
    "Фото 1",
    "Фото 2",
    "Фото 3",
    "Ссылка на сообщение",
    "Поступило",
]

# 1-based номера столбцов «Фото 1/2/3» (для ширины колонок в build_xlsx). Совпадают с
# позицией в _HEADERS: … Кол-во фото(12) · Фото1(13) · Фото2(14) · Фото3(15) · …
_PHOTO_COLS = (13, 14, 15)


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


def _abs_photo_url(inc: Incident, base_url: str, idx: int) -> str:
    """Полный публичный URL фото №idx (0-based) или '' если фото нет.

    photo_urls хранит относительные пути /api/v1/intake/photo/{id}/{i}.jpg → добавляем
    base_url (схема+домен). Плейсхолдеры демо-сида (placeholder://…) — реального файла нет,
    возвращаем ''. Эндпоинт отдачи фото публичный, URL открывается без авторизации.
    """
    urls = inc.photo_urls or []
    if idx >= len(urls):
        return ""
    u = urls[idx]
    if not isinstance(u, str) or not u:
        return ""
    if u.startswith("http"):
        return u
    if u.startswith("/"):
        return f"{base_url.rstrip('/')}{u}"
    return ""


def _photo_image_cell(inc: Incident, base_url: str, idx: int):
    """Ячейка столбца «Фото N»: формула =IMAGE(url) — Excel 365/Online показывает картинку
    по URL прямо в ячейке. Нет фото → пустая ячейка.

    Префикс `_xlfn.` ОБЯЗАТЕЛЕН: IMAGE введена в Excel 2022, в формате xlsx новые функции
    хранятся как `_xlfn.IMAGE`, иначе Excel покажет #ИМЯ?/@IMAGE. В Excel 2019/2021 и
    МойОфис/Р7 функция не поддерживается (там будет #ИМЯ? — по выбору пользователя).
    """
    url = _abs_photo_url(inc, base_url, idx)
    if not url:
        return ""
    # URL кавычек не содержит; на всякий случай убираем, чтобы не порвать формулу.
    safe = url.replace('"', "")
    return f'=_xlfn.IMAGE("{safe}","Фото {idx + 1}")'


def _received(inc: Incident) -> str:
    if inc.received_at is None:
        return ""
    return inc.received_at.strftime("%Y-%m-%d %H:%M")


def _row(inc: Incident, base_url: str) -> list:
    return [
        inc.fio,
        _SOURCE_LABELS.get(inc.source, inc.source),
        _STATUS_LABELS.get(inc.status, inc.status),
        inc.region,
        inc.city,
        inc.street,
        _full_addr(inc),
        inc.coords,
        inc.comment or "",
        _photo_date(inc),
        _photo_time(inc),
        inc.photos,
        _photo_image_cell(inc, base_url, 0),
        _photo_image_cell(inc, base_url, 1),
        _photo_image_cell(inc, base_url, 2),
        _message_link(inc),
        _received(inc),
    ]


def build_xlsx(rows: Iterable[Incident], base_url: str = "") -> bytes:
    """Строит .xlsx (bytes) из инцидентов. 17 колонок, первая строка — заголовки.

    base_url (схема+домен, напр. https://ecopulse.reo.ru) — для абсолютных URL фото.
    Столбцы «Фото 1/2/3» несут формулу =IMAGE(url): Excel 365/Online рисует картинку в
    ячейке. Под превью расширяем эти столбцы и поднимаем высоту строк, где есть фото.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Инциденты"

    ws.append(_HEADERS)
    row_idx = 1
    for inc in rows:
        row_idx += 1
        ws.append(_row(inc, base_url))
        # Строку с ≥1 фото делаем выше — чтобы превью =IMAGE было видно, а не в «щёлку».
        if any(_abs_photo_url(inc, base_url, i) for i in range(3)):
            ws.row_dimensions[row_idx].height = 80

    # Ширина 3 столбцов «Фото» под квадратное превью (≈80px).
    for col in _PHOTO_COLS:
        ws.column_dimensions[get_column_letter(col)].width = 14

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
