"""Валидность миграций Alembic — офлайн (без БД).

Модули версий грузятся по файлу (имена начинаются с цифр — не импортируются как
пакет). Проверяем цепочку ревизий (единственный head) и что 0016 добавляет/сносит
incidents.mno_id + индекс ix_incidents_mno_id, а 0017 — mno.source, вызывая
upgrade/downgrade с поддельным alembic.op (реальных запросов к БД нет).
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"


def _load(filename: str):
    """Грузит модуль миграции по имени файла (spec_from_file_location)."""
    path = VERSIONS / filename
    spec = importlib.util.spec_from_file_location(f"mig_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _all_migrations():
    return [_load(p.name) for p in sorted(VERSIONS.glob("[0-9][0-9][0-9][0-9]_*.py"))]


def test_migration_chain_single_head_is_0021():
    """Цепочка ревизий консистентна: ровно один head, и это 0021 (0021→0020→…)."""
    modules = _all_migrations()
    revs = {m.revision for m in modules}
    downs = {m.down_revision for m in modules if m.down_revision}
    heads = revs - downs
    assert heads == {"0021"}
    # Каждая down_revision указывает на существующую ревизию (нет разрывов цепочки).
    assert downs <= revs


def test_0016_revision_identifiers():
    m = _load("0016_incident_mno_id.py")
    assert m.revision == "0016"
    assert m.down_revision == "0015"


def test_0016_upgrade_adds_mno_id_and_index(monkeypatch):
    """upgrade(): add_column incidents.mno_id (nullable) + create_index ix_incidents_mno_id."""
    m = _load("0016_incident_mno_id.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.upgrade()

    fake_op.add_column.assert_called_once()
    table, column = fake_op.add_column.call_args.args
    assert table == "incidents"
    assert column.name == "mno_id"
    assert column.nullable is True
    fake_op.create_index.assert_called_once_with(
        "ix_incidents_mno_id", "incidents", ["mno_id"]
    )


def test_0016_downgrade_drops_index_and_column(monkeypatch):
    """downgrade(): drop_index ix_incidents_mno_id + drop_column incidents.mno_id."""
    m = _load("0016_incident_mno_id.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.downgrade()

    fake_op.drop_index.assert_called_once_with(
        "ix_incidents_mno_id", table_name="incidents"
    )
    fake_op.drop_column.assert_called_once_with("incidents", "mno_id")


def test_0017_revision_identifiers():
    m = _load("0017_mno_source.py")
    assert m.revision == "0017"
    assert m.down_revision == "0016"


def test_0017_upgrade_adds_mno_source(monkeypatch):
    """upgrade(): add_column mno.source String(16) NOT NULL server_default 'fgis'."""
    m = _load("0017_mno_source.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.upgrade()

    fake_op.add_column.assert_called_once()
    table, column = fake_op.add_column.call_args.args
    assert table == "mno"
    assert column.name == "source"
    assert column.nullable is False
    # server_default 'fgis' — существующие МНО бэкфиллятся как из ФГИС/по умолчанию.
    assert column.server_default.arg == "fgis"


def test_0017_downgrade_drops_source(monkeypatch):
    """downgrade(): drop_column mno.source."""
    m = _load("0017_mno_source.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.downgrade()

    fake_op.drop_column.assert_called_once_with("mno", "source")


def test_0018_revision_identifiers():
    m = _load("0018_mno_comment_photos.py")
    assert m.revision == "0018"
    assert m.down_revision == "0017"


def test_0018_upgrade_adds_comment_and_photo_urls(monkeypatch):
    """upgrade(): add_column mno.comment (Text, NULLABLE) + mno.photo_urls (JSONB, NOT NULL)."""
    m = _load("0018_mno_comment_photos.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.upgrade()

    assert fake_op.add_column.call_count == 2
    cols = {c.args[1].name: c.args[1] for c in fake_op.add_column.call_args_list}
    assert set(cols) == {"comment", "photo_urls"}
    assert cols["comment"].nullable is True
    assert cols["photo_urls"].nullable is False
    # server_default '[]'::jsonb — существующие МНО бэкфиллятся пустым списком фото.
    assert "[]" in str(cols["photo_urls"].server_default.arg)


def test_0018_downgrade_drops_comment_and_photo_urls(monkeypatch):
    """downgrade(): drop_column mno.photo_urls + mno.comment."""
    m = _load("0018_mno_comment_photos.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.downgrade()

    dropped = {c.args for c in fake_op.drop_column.call_args_list}
    assert dropped == {("mno", "photo_urls"), ("mno", "comment")}


def test_0019_revision_identifiers():
    m = _load("0019_volunteer_authored.py")
    assert m.revision == "0019"
    assert m.down_revision == "0018"


def test_0019_upgrade_adds_volunteer_id_to_both_tables(monkeypatch):
    """upgrade(): add_column incidents.volunteer_id + mno.volunteer_id (оба nullable UUID)
    и оба индекса ix_incidents_volunteer_id / ix_mno_volunteer_id."""
    m = _load("0019_volunteer_authored.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.upgrade()

    # Две колонки volunteer_id — по одной в incidents и mno.
    assert fake_op.add_column.call_count == 2
    added = {c.args[0]: c.args[1] for c in fake_op.add_column.call_args_list}
    assert set(added) == {"incidents", "mno"}
    for table, column in added.items():
        assert column.name == "volunteer_id"
        assert column.nullable is True
    # Оба индекса под фильтр «мои» по volunteer_id (columns — list, потому мапой, не set).
    indexes = {
        c.args[0]: (c.args[1], c.args[2])
        for c in fake_op.create_index.call_args_list
    }
    assert indexes == {
        "ix_incidents_volunteer_id": ("incidents", ["volunteer_id"]),
        "ix_mno_volunteer_id": ("mno", ["volunteer_id"]),
    }


def test_0019_downgrade_drops_indexes_and_columns(monkeypatch):
    """downgrade(): сносит оба индекса и обе колонки volunteer_id (в обратном порядке)."""
    m = _load("0019_volunteer_authored.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.downgrade()

    dropped_idx = {c.args for c in fake_op.drop_index.call_args_list}
    assert dropped_idx == {
        ("ix_mno_volunteer_id",),
        ("ix_incidents_volunteer_id",),
    }
    # table_name передан именованным аргументом.
    for call in fake_op.drop_index.call_args_list:
        assert call.kwargs["table_name"] in ("mno", "incidents")
    dropped_col = {c.args for c in fake_op.drop_column.call_args_list}
    assert dropped_col == {("mno", "volunteer_id"), ("incidents", "volunteer_id")}


def test_0020_revision_identifiers():
    m = _load("0020_smtp_settings.py")
    assert m.revision == "0020"
    assert m.down_revision == "0019"


def test_0020_upgrade_creates_smtp_settings(monkeypatch):
    """upgrade(): create_table smtp_settings со всеми колонками (пароль — password_enc)."""
    m = _load("0020_smtp_settings.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.upgrade()

    fake_op.create_table.assert_called_once()
    args = fake_op.create_table.call_args.args
    assert args[0] == "smtp_settings"
    col_names = {c.name for c in args[1:] if hasattr(c, "name")}
    assert {
        "id", "host", "port", "encryption", "username", "password_enc",
        "from_email", "from_name", "status", "last_test_at", "last_test_ok",
        "last_test_error", "created_at", "updated_at",
    } <= col_names
    # Пароль хранится только зашифрованным (password_enc), открытого поля нет.
    assert "password" not in col_names


def test_0020_downgrade_drops_smtp_settings(monkeypatch):
    """downgrade(): drop_table smtp_settings."""
    m = _load("0020_smtp_settings.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.downgrade()

    fake_op.drop_table.assert_called_once_with("smtp_settings")


def test_0021_revision_identifiers():
    m = _load("0021_reports.py")
    assert m.revision == "0021"
    assert m.down_revision == "0020"


def test_0021_upgrade_creates_reports(monkeypatch):
    """upgrade(): create_table reports со всеми колонками (файл на диске по id)."""
    m = _load("0021_reports.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.upgrade()

    fake_op.create_table.assert_called_once()
    args = fake_op.create_table.call_args.args
    assert args[0] == "reports"
    col_names = {c.name for c in args[1:] if hasattr(c, "name")}
    assert {
        "id", "kind", "filename", "row_count", "size_bytes",
        "created_by_id", "created_by_fio", "created_at",
    } <= col_names


def test_0021_downgrade_drops_reports(monkeypatch):
    """downgrade(): drop_table reports."""
    m = _load("0021_reports.py")
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.downgrade()

    fake_op.drop_table.assert_called_once_with("reports")
