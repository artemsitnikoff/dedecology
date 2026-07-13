"""Тесты выгрузки в формате УТКО (build_utko_xlsx) — офлайн, без БД."""

from datetime import datetime, timezone
from io import BytesIO

from openpyxl import load_workbook

from app.models import Incident
from app.services.utko_export import build_utko_xlsx


def _incident(**kw) -> Incident:
    base = dict(
        source="form",
        status="new",
        fio="Иванов Иван",
        region="Самарская область",
        city="г. Кинель",
        street="ул. Маяковского, 41",
        coords="53.2, 50.6",
        mno_reg="63-04-001162",
        incident_type="fire",
        comment="Возгорание в контейнере",
        photo_time=datetime(2026, 4, 26, 8, 5, tzinfo=timezone.utc),
        photos=2,
        photo_urls=[
            "/api/v1/intake/photo/abc/0.jpg",
            "/api/v1/intake/photo/abc/1.jpg",
        ],
        received_at=datetime(2026, 4, 26, 8, 11, tzinfo=timezone.utc),
    )
    base.update(kw)
    return Incident(**base)


_EXPECTED_HEADERS = [
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


def _rows(rows, base_url=""):
    wb = load_workbook(BytesIO(build_utko_xlsx(rows, base_url, {"fire": "Возгорание в контейнере"})))
    return wb.active


def test_utko_headers_exact_order():
    ws = _rows([])
    headers = [c.value for c in next(ws.iter_rows(max_row=1))]
    assert headers == _EXPECTED_HEADERS


def test_utko_template_header_intact_data_from_row_5():
    """Шапка шаблона (строки 1–4) не трогается, данные — строго с 5-й строки."""
    inc = _incident()
    ws = _rows([inc])
    # лист данных из шаблона
    assert ws.title == "Реестр для инцидентов"
    # строки 2–4 — фиксированная шапка шаблона (гвоздями): номера · типы · обязательность
    assert ws.cell(row=2, column=1).value == 1
    assert ws.cell(row=3, column=1).value == "Список"
    assert ws.cell(row=4, column=1).value == "Обязательное поле"
    # первая строка данных — 5-я
    assert ws.cell(row=5, column=1).value == "Самарская область"
    assert ws.cell(row=5, column=2).value == "63-04-001162"


def test_utko_row_maps_fields_and_photo_urls():
    inc = _incident()
    ws = _rows([inc], base_url="https://ecopulse.reo.ru")
    row = [c.value for c in next(ws.iter_rows(min_row=5))]
    assert row[0] == "Самарская область"          # Субъект РФ
    assert row[1] == "63-04-001162"               # Реестровый номер МНО
    assert row[2] == "26.04.2026 08:05"           # Дата и время фотофиксации
    assert row[3] == "г. Кинель, ул. Маяковского, 41"  # Адрес (город + улица)
    assert row[4] == "Возгорание в контейнере"    # Тип инцидента (по type_labels)
    assert row[5] in (None, "")                    # Подтип — пусто (поля нет)
    assert row[6] == "Возгорание в контейнере"    # Описание (comment)
    # 6 столбцов «Ссылка на фото»: 2 полных URL + 4 пустых.
    assert row[7] == "https://ecopulse.reo.ru/api/v1/intake/photo/abc/0.jpg"
    assert row[8] == "https://ecopulse.reo.ru/api/v1/intake/photo/abc/1.jpg"
    assert all(row[i] in (None, "") for i in range(9, 13))


def test_utko_subject_from_our_directory_by_mno():
    """«Субъект РФ» берётся из справочника (region_by_mno по mno_id), а не из inc.region (DaData)."""
    from uuid import uuid4

    mid = uuid4()
    inc = _incident(region="Самарская обл (DaData)", mno_id=mid)
    wb = load_workbook(
        BytesIO(
            build_utko_xlsx([inc], "", {"fire": "x"}, region_by_mno={mid: "Самарская область"})
        )
    )
    row = [c.value for c in next(wb.active.iter_rows(min_row=5))]
    assert row[0] == "Самарская область"  # из нашего справочника (как в УТКО), НЕ DaData

    # Нет соответствия в справочнике / нет карты → фолбэк на inc.region.
    wb2 = load_workbook(BytesIO(build_utko_xlsx([inc], "", {"fire": "x"}, region_by_mno={})))
    row2 = [c.value for c in next(wb2.active.iter_rows(min_row=5))]
    assert row2[0] == "Самарская обл (DaData)"


def test_utko_subtype_label_for_no_access():
    """incident_subtype='blocked_by_car' → в колонке «Подтип инцидента» его подпись."""
    inc = _incident(incident_type="no_access", incident_subtype="blocked_by_car")
    ws = _rows([inc])
    row = [c.value for c in next(ws.iter_rows(min_row=5))]
    assert row[5] == "Проезд заблокирован автомобилем"  # Подтип из справочника


def test_utko_subtype_empty_when_absent():
    """Без подтипа (incident_subtype=None) колонка «Подтип инцидента» пуста."""
    inc = _incident(incident_subtype=None)
    ws = _rows([inc])
    row = [c.value for c in next(ws.iter_rows(min_row=5))]
    assert row[5] in (None, "")


def test_utko_skips_placeholder_photos():
    inc = _incident(photos=1, photo_urls=["placeholder://incident-photo/1"])
    ws = _rows([inc], base_url="https://ecopulse.reo.ru")
    row = [c.value for c in next(ws.iter_rows(min_row=5))]
    assert all(row[i] in (None, "") for i in range(7, 13))  # плейсхолдер → все ссылки пусты
