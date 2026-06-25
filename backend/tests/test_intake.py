"""Тесты публичного приёма Яндекс-Формы (/api/v1/intake/yandex) — офлайн.

Сервис create_incident_from_form мокается на границе роута; разбор параметров
проверяется отдельным прямым вызовом сервиса (без БД).
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.config import settings
from app.models import Incident
from app.services.intake import create_incident_from_form

_SAMPLE_PARAMS = {
    "full_address": "Самарская область, г. Кинель, ул. Маяковского, 41",
    "coords": "53.2,50.6",
    "photo_time": "26.04.2026, 08:05",
    "fio": "Иванов Иван",
    "bins": "да",
    "photos": "https://x/1.jpg\nhttps://x/2.jpg",
}

_SAMPLE_BODY = {
    "jsonrpc": "2.0",
    "method": "incident.create",
    "params": _SAMPLE_PARAMS,
    "id": 1,
}


@pytest.mark.asyncio
async def test_yandex_intake_valid_token(client, monkeypatch):
    """Валидный токен + JSON-RPC тело → 200, result.ok, сервис вызван с params."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")

    fake_incident = Incident(source="form", status="new")
    fake_incident.id = uuid4()
    create = AsyncMock(return_value=fake_incident)

    with patch(
        "app.api.v1.intake.intake_service.create_incident_from_form",
        new=create,
    ):
        resp = await client.post(
            "/api/v1/intake/yandex",
            headers={"X-Intake-Token": "secret-token"},
            json=_SAMPLE_BODY,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert body["result"]["ok"] is True
    assert body["result"]["incident_id"] == str(fake_incident.id)

    # Роутер развернул конверт и передал params в сервис.
    create.assert_awaited_once()
    passed_params = create.call_args.args[1]
    assert passed_params["full_address"] == _SAMPLE_PARAMS["full_address"]
    assert passed_params["fio"] == "Иванов Иван"


@pytest.mark.asyncio
async def test_yandex_intake_wrong_token_403(client, monkeypatch):
    """Неверный X-Intake-Token → 403 FORBIDDEN, сервис не вызывается."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    create = AsyncMock()
    with patch(
        "app.api.v1.intake.intake_service.create_incident_from_form",
        new=create,
    ):
        resp = await client.post(
            "/api/v1/intake/yandex",
            headers={"X-Intake-Token": "WRONG"},
            json=_SAMPLE_BODY,
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_yandex_intake_missing_token_403(client, monkeypatch):
    """Отсутствующий заголовок X-Intake-Token → 403."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    resp = await client.post("/api/v1/intake/yandex", json=_SAMPLE_BODY)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_yandex_intake_disabled_when_unset(client, monkeypatch):
    """Токен не сконфигурирован на сервере → 503 INTAKE_DISABLED."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", None)
    resp = await client.post(
        "/api/v1/intake/yandex",
        headers={"X-Intake-Token": "anything"},
        json=_SAMPLE_BODY,
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "INTAKE_DISABLED"


@pytest.mark.asyncio
async def test_create_incident_from_form_parses_params(fake_session):
    """Прямой вызов сервиса (без БД): разбор адреса/баков/фото/времени."""
    # add — синхронный в реальном SQLAlchemy; делаем sync-моком (без корутин).
    fake_session.add = MagicMock()

    incident = await create_incident_from_form(fake_session, _SAMPLE_PARAMS)

    assert incident.source == "form"
    assert incident.status == "new"
    assert incident.fio == "Иванов Иван"
    assert incident.region == "Самарская область"
    assert incident.city == "г. Кинель"
    assert incident.street == "ул. Маяковского, 41"
    assert incident.coords == "53.2,50.6"
    assert incident.bins is True
    assert incident.photo_urls == ["https://x/1.jpg", "https://x/2.jpg"]
    assert incident.photos == 2
    assert incident.photo_time is not None
    assert incident.photo_time.tzinfo is not None
    assert (incident.photo_time.year, incident.photo_time.month, incident.photo_time.day) == (
        2026,
        4,
        26,
    )

    # Инцидент добавлен в сессию, flush выполнен (incident + audit).
    assert fake_session.add.called
    fake_session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_create_incident_from_form_tolerant_defaults(fake_session):
    """Толерантность: пустые/нетиповые значения → безопасные дефолты."""
    fake_session.add = MagicMock()

    incident = await create_incident_from_form(
        fake_session,
        {
            "full_address": "Только одна строка адреса",
            "bins": "может быть",
            "photo_time": "не дата",
            "photos": None,
        },
    )

    assert incident.region == ""
    assert incident.city == ""
    assert incident.street == "Только одна строка адреса"
    assert incident.fio == ""
    assert incident.coords == ""
    assert incident.bins is None  # нераспознанное значение
    assert incident.photo_time is None  # неразбираемое
    assert incident.photo_urls == []
    assert incident.photos == 0
