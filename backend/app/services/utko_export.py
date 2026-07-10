"""Выгрузка обращений в формате ФГИС УТКО (.xlsx) — плоская таблица под загрузку в УТКО.

Отличается от обычного экспорта инцидентов (services/export.py): фиксированный порядок
колонок УТКО, дата+время фотофиксации одной ячейкой, до 6 столбцов «Ссылка на фото» —
ПРОСТО текстовые полные URL (без встраивания картинок и формул). «Подтип инцидента» —
подпись из справочника services/incident_subtypes.py (только у типа no_access; иначе "").
"""

from io import BytesIO
from typing import Iterable

from openpyxl import Workbook

from ..models import Incident
from .incident_subtypes import label_for as _subtype_label
from .incident_types import incident_type_label as _static_type_label

# Заголовки в точном порядке формата УТКО (6 столбцов «Ссылка на фото» — под макс. число фото).
_HEADERS = [
    "Субъект РФ",
    "Реестровый номер МНО",
    "Дата и время фотофиксации",
    "Адрес",
    "Тип инцидента",
    "Подтип инцидента",
    "Описание",
    "Ссылка на фото",
    "Ссылка на фото",
    "Ссылка на фото",
    "Ссылка на фото",
    "Ссылка на фото",
    "Ссылка на фото",
]
_PHOTO_SLOTS = 6  # столбцов «Ссылка на фото»


def _photo_datetime(inc: Incident) -> str:
    """«ДД.ММ.ГГГГ ЧЧ:ММ» или '' если фотофиксации нет."""
    if inc.photo_time is None:
        return ""
    return inc.photo_time.strftime("%d.%m.%Y %H:%M")


def _address(inc: Incident) -> str:
    """Адрес без субъекта РФ (он отдельной колонкой): город + улица."""
    return ", ".join(p for p in [inc.city, inc.street] if p)


def _type_label(inc: Incident, type_labels: dict | None) -> str:
    code = inc.incident_type
    if not code:
        return ""
    if type_labels and code in type_labels:
        return type_labels[code]
    return _static_type_label(code) or code


def _abs_url(u, base_url: str) -> str:
    """Полный публичный URL фото или '' (плейсхолдеры сида/мусор → '')."""
    if not isinstance(u, str) or not u:
        return ""
    if u.startswith("http"):
        return u
    if u.startswith("/"):
        return f"{base_url.rstrip('/')}{u}"
    return ""


def _photo_urls(inc: Incident, base_url: str) -> list[str]:
    """До _PHOTO_SLOTS полных URL фото; недостающие — пустые строки (ровно _PHOTO_SLOTS)."""
    urls = [_abs_url(u, base_url) for u in (inc.photo_urls or [])]
    urls = [u for u in urls if u][:_PHOTO_SLOTS]
    return urls + [""] * (_PHOTO_SLOTS - len(urls))


def _subject(inc: Incident, region_by_mno: dict | None) -> str:
    """Субъект РФ КАК В УТКО: из нашего справочника по МНО инцидента; фолбэк — inc.region."""
    if region_by_mno and getattr(inc, "mno_id", None):
        name = region_by_mno.get(inc.mno_id)
        if name:
            return name
    return inc.region


def _row(inc: Incident, base_url: str, type_labels: dict | None, region_by_mno: dict | None) -> list:
    return [
        _subject(inc, region_by_mno),
        inc.mno_reg or "",
        _photo_datetime(inc),
        _address(inc),
        _type_label(inc, type_labels),
        _subtype_label(inc.incident_subtype),  # Подтип (только у типа no_access; иначе "")
        inc.comment or "",
        *_photo_urls(inc, base_url),
    ]


def build_utko_xlsx(
    rows: Iterable[Incident],
    base_url: str = "",
    type_labels: dict | None = None,
    region_by_mno: dict | None = None,
) -> bytes:
    """Строит .xlsx (bytes) в формате УТКО. Ссылки на фото — просто текстовые URL.

    region_by_mno — {mno_id: имя субъекта из НАШЕГО справочника (синхр. из УТКО)} для
    колонки «Субъект РФ» (как в УТКО, не DaData-текстом инцидента); None → фолбэк inc.region.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Выгрузка УТКО"

    ws.append(_HEADERS)
    for inc in rows:
        ws.append(_row(inc, base_url, type_labels, region_by_mno))

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
