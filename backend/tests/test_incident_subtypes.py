"""Тесты фиксированного справочника подтипов инцидента + публичного эндпоинта.

Подтипы заданы жёстко в коде (services/incident_subtypes.py) — есть только у типа
no_access. Офлайн, без БД.
"""

import pytest

from app.services.incident_subtypes import (
    INCIDENT_SUBTYPES,
    is_valid_subtype,
    label_for,
    subtypes_for,
)


# --- Константа-справочник и хелперы -------------------------------------------


def test_subtypes_for_no_access_has_two():
    """У типа no_access ровно 2 подтипа в фиксированном порядке."""
    subs = subtypes_for("no_access")
    assert [s["code"] for s in subs] == ["blocked_by_car", "other_reason"]
    assert all(s["label"].strip() for s in subs)


def test_subtypes_for_other_type_empty():
    """У типа без подтипов (напр. fire) → пустой список."""
    assert subtypes_for("fire") == []
    assert subtypes_for("") == []


def test_label_for_resolves_and_defaults_empty():
    """label_for: известный код → подпись; пусто/None/неизвестный → ""."""
    assert label_for("blocked_by_car") == "Проезд заблокирован автомобилем"
    assert label_for("other_reason") == "Иная причина"
    assert label_for("") == ""
    assert label_for(None) == ""
    assert label_for("nope") == ""


def test_is_valid_subtype():
    """is_valid_subtype: код принадлежит подтипам ИМЕННО этого типа."""
    assert is_valid_subtype("no_access", "other_reason") is True
    assert is_valid_subtype("no_access", "blocked_by_car") is True
    assert is_valid_subtype("no_access", "xxx") is False
    assert is_valid_subtype("no_access", "") is False
    # Валидный код подтипа, но не для этого типа → False.
    assert is_valid_subtype("fire", "blocked_by_car") is False


def test_constant_shape():
    """INCIDENT_SUBTYPES — {type_code: [{code, label}]}, только no_access."""
    assert set(INCIDENT_SUBTYPES) == {"no_access"}
    for subs in INCIDENT_SUBTYPES.values():
        for s in subs:
            assert set(s) == {"code", "label"}


# --- Публичный GET /intake/incident-subtypes ----------------------------------


@pytest.mark.asyncio
async def test_public_incident_subtypes_endpoint(client):
    """GET /intake/incident-subtypes → 200, словарь с no_access и 2 подтипами."""
    resp = await client.get("/api/v1/intake/incident-subtypes")
    assert resp.status_code == 200
    data = resp.json()
    assert "no_access" in data
    assert [s["code"] for s in data["no_access"]] == [
        "blocked_by_car",
        "other_reason",
    ]
