"""Тесты бэкфилла УТКО-копий фото (app.backfill_utko_photos) — офлайн, без БД.

Чистый обход файловой системы: синтетические JPEG-фото инцидентов во временном
STORAGE_DIR, проверяем создание недостающих `{i}_utko.jpg`, идемпотентность и --force.
"""

import os
from io import BytesIO

import pytest
from PIL import Image

from app.config import settings
from app.backfill_utko_photos import backfill
from app.services.intake import _UTKO_MAX_BYTES


def _jpeg(path, size=(1200, 900), color=(0, 120, 0)) -> None:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    path.write_bytes(buf.getvalue())


def _make_incident_dir(tmp_path, iid: str, n_full: int):
    """Каталог инцидента с n_full FULL-фото `{i}.jpg` (без УТКО-копий)."""
    inc_dir = tmp_path / "incidents" / iid
    inc_dir.mkdir(parents=True)
    for i in range(n_full):
        _jpeg(inc_dir / f"{i}.jpg")
    return inc_dir


def test_backfill_creates_missing_utko(monkeypatch, tmp_path):
    """Бэкфилл создаёт недостающие `{i}_utko.jpg` для каждого FULL, ≤500000 байт."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    inc_dir = _make_incident_dir(tmp_path, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", 3)

    created, skipped, errors = backfill(force=False)
    assert (created, skipped, errors) == (3, 0, 0)
    for i in range(3):
        dest = inc_dir / f"{i}_utko.jpg"
        assert dest.is_file()
        assert os.path.getsize(dest) <= _UTKO_MAX_BYTES


def test_backfill_idempotent_second_run_skips(monkeypatch, tmp_path):
    """Повторный прогон без --force ничего не пересобирает (все пропущены)."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    _make_incident_dir(tmp_path, "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", 2)

    first = backfill(force=False)
    assert first == (2, 0, 0)
    second = backfill(force=False)
    assert second == (0, 2, 0)  # созданного нет, оба пропущены


def test_backfill_force_rebuilds(monkeypatch, tmp_path):
    """--force пересобирает УТКО-копии даже когда они уже есть."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    _make_incident_dir(tmp_path, "cccccccc-cccc-cccc-cccc-cccccccccccc", 2)

    backfill(force=False)
    created, skipped, errors = backfill(force=True)
    assert (created, skipped, errors) == (2, 0, 0)  # оба пересобраны, не пропущены


def test_backfill_ignores_thumb_and_utko_sources(monkeypatch, tmp_path):
    """Бэкфилл берёт исходником только FULL `{i}.jpg` — не THUMB и не сам `_utko`."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    inc_dir = tmp_path / "incidents" / "dddddddd-dddd-dddd-dddd-dddddddddddd"
    inc_dir.mkdir(parents=True)
    _jpeg(inc_dir / "0.jpg")
    _jpeg(inc_dir / "0_thumb.jpg")  # не должен породить `0_thumb_utko.jpg`

    created, skipped, errors = backfill(force=False)
    assert created == 1  # только из 0.jpg
    assert (inc_dir / "0_utko.jpg").is_file()
    assert not (inc_dir / "0_thumb_utko.jpg").exists()


def test_backfill_no_incidents_dir(monkeypatch, tmp_path):
    """Нет каталога incidents → прогон не падает, нулевая сводка."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    assert backfill(force=False) == (0, 0, 0)


def test_backfill_one_bad_file_does_not_abort(monkeypatch, tmp_path):
    """Битый `{i}.jpg` (не открывается Pillow) считается ошибкой, но не роняет прогон."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    inc_dir = tmp_path / "incidents" / "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    inc_dir.mkdir(parents=True)
    (inc_dir / "0.jpg").write_bytes(b"not a real jpeg")  # битый
    _jpeg(inc_dir / "1.jpg")  # валидный

    created, skipped, errors = backfill(force=False)
    assert created == 1  # валидный обработан
    assert errors == 1   # битый учтён как ошибка, прогон продолжился
    assert (inc_dir / "1_utko.jpg").is_file()
