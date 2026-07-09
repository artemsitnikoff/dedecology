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


def test_utko_row_maps_fields_and_photo_urls():
    inc = _incident()
    ws = _rows([inc], base_url="https://ecopulse.reo.ru")
    row = [c.value for c in next(ws.iter_rows(min_row=2))]
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


def test_utko_skips_placeholder_photos():
    inc = _incident(photos=1, photo_urls=["placeholder://incident-photo/1"])
    ws = _rows([inc], base_url="https://ecopulse.reo.ru")
    row = [c.value for c in next(ws.iter_rows(min_row=2))]
    assert all(row[i] in (None, "") for i in range(7, 13))  # плейсхолдер → все ссылки пусты
