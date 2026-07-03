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


def test_migration_chain_single_head_is_0017():
    """Цепочка ревизий консистентна: ровно один head, и это 0017 (0017→0016→…)."""
    modules = _all_migrations()
    revs = {m.revision for m in modules}
    downs = {m.down_revision for m in modules if m.down_revision}
    heads = revs - downs
    assert heads == {"0017"}
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
