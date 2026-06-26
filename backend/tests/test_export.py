"""Тесты серверного .xlsx-экспорта — офлайн, без БД (build_xlsx над Incident)."""

from datetime import datetime, timezone
from io import BytesIO

from openpyxl import load_workbook

from app.models import Incident
from app.services.export import build_xlsx

# 0-based индекс колонки «Ссылка на сообщение» в порядке ТЗ §7 (12-я колонка).
_MSG_LINK_COL = 11


def _incident(**kw) -> Incident:
    base = dict(
        source="max",
        status="new",
        fio="Иванов Иван",
        region="Самарская обл",
        city="г Кинель",
        street="ул Маяковского, д 41",
        coords="53.2, 50.6",
        photo_time=datetime(2026, 4, 26, 8, 5, tzinfo=timezone.utc),
        photos=1,
        msg="mid.ffff0001",
        msg_url=None,
        received_at=datetime(2026, 4, 26, 8, 11, tzinfo=timezone.utc),
    )
    base.update(kw)
    return Incident(**base)


def _link_cells(rows: list[Incident]) -> list:
    """Возвращает значения колонки «Ссылка на сообщение» (без строки заголовков)."""
    wb = load_workbook(BytesIO(build_xlsx(rows)))
    ws = wb.active
    return [row[_MSG_LINK_COL].value for row in ws.iter_rows(min_row=2)]


def test_export_writes_msg_url_as_is():
    """msg_url непустой → попадает в колонку «Ссылка на сообщение» КАК ЕСТЬ."""
    url = "https://max.ru/c/-75787158905457/AZ8DNeZnbkM"
    inc = _incident(msg_url=url)
    assert _link_cells([inc]) == [url]


def test_export_blank_msg_url_writes_empty_not_mid_link():
    """msg_url пуст → пустая строка в колонке; БИТАЯ https://max.ru/m/{mid} НЕ строится."""
    inc = _incident(msg="mid.ffffdead", msg_url=None)
    cells = _link_cells([inc])
    # Колонка пустая (openpyxl отдаёт None для "") — главное: НЕ ссылка на mid.
    assert cells[0] in (None, "")
    assert "max.ru/m/" not in (cells[0] or "")
    assert "mid.ffffdead" not in (cells[0] or "")
