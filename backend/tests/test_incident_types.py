"""Тесты справочника типов инцидента + публичного эндпоинта /intake/incident-types."""

import pytest

from app.services.incident_types import (
    INCIDENT_TYPES,
    incident_type_label,
    is_valid_incident_type,
    list_incident_types,
)

# Ожидаемые коды в фиксированном порядке (контракт справочника).
_EXPECTED_CODES = [
    "no_access",
    "blocked_access",
    "no_container",
    "fire",
    "non_tko_in_container",
    "damaged_container",
    "waste_nearby",
    "non_tko_on_site",
    "overflow",
    "other",
]


def test_incident_types_has_ten_entries_in_order():
    """10 записей, порядок кодов фиксирован, у каждой есть непустой label."""
    assert len(INCIDENT_TYPES) == 10
    assert [t["code"] for t in INCIDENT_TYPES] == _EXPECTED_CODES
    assert all(t["label"].strip() for t in INCIDENT_TYPES)


def test_is_valid_incident_type():
    """Известный код → True; неизвестный/пустой → False."""
    assert is_valid_incident_type("fire") is True
    assert is_valid_incident_type("other") is True
    assert is_valid_incident_type("nope") is False
    assert is_valid_incident_type("") is False


def test_incident_type_label_resolves_and_falls_back():
    """Резолв кода → подпись; None/пусто/мусор → ""."""
    assert incident_type_label("fire") == "Возгорание в контейнере"
    assert incident_type_label("other") == "Иное"
    assert incident_type_label(None) == ""
    assert incident_type_label("") == ""
    assert incident_type_label("nope") == ""


def test_list_incident_types_returns_full_dicts():
    """list_incident_types → 10 записей вида {code, label}, первая — no_access."""
    lst = list_incident_types()
    assert len(lst) == 10
    assert lst[0] == {"code": "no_access", "label": "Отсутствует доступ к МНО"}
    assert all(set(t.keys()) == {"code", "label"} for t in lst)


@pytest.mark.asyncio
async def test_incident_types_endpoint_returns_ten(client):
    """GET /intake/incident-types → 200 + 10 записей {code, label} в порядке справочника."""
    resp = await client.get("/api/v1/intake/incident-types")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 10
    assert [t["code"] for t in data] == _EXPECTED_CODES
    assert data[3] == {"code": "fire", "label": "Возгорание в контейнере"}
