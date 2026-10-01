"""Тесты УТКО-совместимого API (ядро) — офлайн: сервисный слой/настройки замоканы.

Покрыто:
  • /connect/token: верные креды→200+токен; неверные/grant_type≠password/не сконфигурено→400;
  • require_utko_auth: нет/битый токен→401, валидный→пропуск;
  • truck-visit-events/query: пусто→count 0; данные→camelCase-поля + пагинация доходят до сервиса;
  • truck-visit-events/confirm: нет обязательного→422; неизвестный eventId→422; eventType вне
    справочника→422; валидно→сохранено;
  • video-events: неизвестный mnoId→422; eventType вне ВИДЕО-справочника→422; один битый элемент→
    весь батч отклонён; валидно→вернулись videoEventUuid.

Все тела ошибок УТКО — СВОЙ формат (errorMessage / success+error), НЕ общий конверт {error:{...}}.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.config import settings
from app.utko import auth as utko_auth
from app.utko import validate as utko_validate

QUERY_URL = "/reo-mno-events/api/v1/integration/truck-visit-events/query"
CONFIRM_URL = "/reo-mno-events/api/v1/integration/truck-visit-events/confirm"
VIDEO_URL = "/reo-mno-events/api/v1.0/video-events"


def _auth_header() -> dict:
    """Валидный УТКО Bearer-токен (подпись = JWT_SECRET, т.к. UTKO_TOKEN_SECRET пуст)."""
    return {"Authorization": f"Bearer {utko_auth.issue_access_token(3600)}"}


@pytest.fixture
def utko_creds(monkeypatch):
    """Сконфигурировать UTKO_* креды на время теста."""
    monkeypatch.setattr(settings, "UTKO_CLIENT_ID", "cid", raising=False)
    monkeypatch.setattr(settings, "UTKO_CLIENT_SECRET", "csecret", raising=False)
    monkeypatch.setattr(settings, "UTKO_USERNAME", "user@reo.ru", raising=False)
    monkeypatch.setattr(settings, "UTKO_PASSWORD", "p@ss", raising=False)


# --- /connect/token --------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_success(client, utko_creds):
    resp = await client.post(
        "/connect/token",
        data={
            "grant_type": "password",
            "username": "user@reo.ru",
            "password": "p@ss",
            "client_id": "cid",
            "client_secret": "csecret",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == settings.UTKO_TOKEN_TTL_SECONDS
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["scope"] == "email offline_access openid profile"
    # Выданный токен действительно декодируется как УТКО-токен.
    assert utko_auth.decode_access_token(body["access_token"]) is not None


@pytest.mark.asyncio
async def test_token_wrong_password_400(client, utko_creds):
    resp = await client.post(
        "/connect/token",
        data={
            "grant_type": "password",
            "username": "user@reo.ru",
            "password": "WRONG",
            "client_id": "cid",
            "client_secret": "csecret",
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert "invalid_grant" in body["errorMessage"]


@pytest.mark.asyncio
async def test_token_wrong_grant_type_400(client, utko_creds):
    resp = await client.post(
        "/connect/token",
        data={
            "grant_type": "client_credentials",
            "username": "user@reo.ru",
            "password": "p@ss",
            "client_id": "cid",
            "client_secret": "csecret",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_token_refresh_grant_success(client, utko_creds):
    """password-grant выдаёт refresh_token, который обменивается на новую пару."""
    r1 = await client.post(
        "/connect/token",
        data={
            "grant_type": "password",
            "username": "user@reo.ru",
            "password": "p@ss",
            "client_id": "cid",
            "client_secret": "csecret",
        },
    )
    refresh = r1.json()["refresh_token"]
    assert utko_auth.decode_refresh_token(refresh) is not None

    r2 = await client.post(
        "/connect/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert utko_auth.decode_access_token(body["access_token"]) is not None
    assert body["refresh_token"]  # выдаётся новая пара


@pytest.mark.asyncio
async def test_token_refresh_grant_bad_token_400(client, utko_creds):
    """Битый refresh_token → 400 (не выдаём пару)."""
    r = await client.post(
        "/connect/token",
        data={"grant_type": "refresh_token", "refresh_token": "garbage"},
    )
    assert r.status_code == 400
    assert r.json()["success"] is False


@pytest.mark.asyncio
async def test_token_access_token_not_valid_as_refresh_400(client, utko_creds):
    """access-токен (typ=utko) нельзя подсунуть как refresh (typ=utko_refresh) → 400."""
    access = utko_auth.issue_access_token(3600)
    r = await client.post(
        "/connect/token",
        data={"grant_type": "refresh_token", "refresh_token": access},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_token_not_configured_400(client, monkeypatch):
    """UTKO_* не заданы → токен не выдаётся (честный 400)."""
    monkeypatch.setattr(settings, "UTKO_CLIENT_ID", None, raising=False)
    monkeypatch.setattr(settings, "UTKO_CLIENT_SECRET", None, raising=False)
    monkeypatch.setattr(settings, "UTKO_USERNAME", None, raising=False)
    monkeypatch.setattr(settings, "UTKO_PASSWORD", None, raising=False)
    resp = await client.post(
        "/connect/token",
        data={
            "grant_type": "password",
            "username": "x",
            "password": "y",
            "client_id": "z",
            "client_secret": "w",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["success"] is False


# --- require_utko_auth -----------------------------------------------------------


@pytest.mark.asyncio
async def test_query_no_token_401(client):
    resp = await client.post(QUERY_URL, json={"filter": {"fromDate": "2026-01-01T00:00:00Z"}})
    assert resp.status_code == 401
    assert resp.json() == {"errorMessage": "Unauthorized"}


@pytest.mark.asyncio
async def test_query_broken_token_401(client):
    resp = await client.post(
        QUERY_URL,
        headers={"Authorization": "Bearer not-a-jwt"},
        json={"filter": {"fromDate": "2026-01-01T00:00:00Z"}},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_access_token_rejected_401(client):
    """Токен приложения (type=access, не typ=utko) не пускают в УТКО-эндпоинты."""
    from app.core.security import create_access_token

    tok = create_access_token({"sub": str(uuid4())})
    resp = await client.post(
        QUERY_URL,
        headers={"Authorization": f"Bearer {tok}"},
        json={"filter": {"fromDate": "2026-01-01T00:00:00Z"}},
    )
    assert resp.status_code == 401


# --- truck-visit-events/query ----------------------------------------------------


@pytest.mark.asyncio
async def test_query_empty_count_zero(client):
    with patch(
        "app.utko.routers.events.service.query_truck_visit_events",
        new=AsyncMock(return_value=(0, [])),
    ):
        resp = await client.post(
            QUERY_URL,
            headers=_auth_header(),
            json={"filter": {"fromDate": "2026-01-01T00:00:00Z"}, "take": 0, "skip": 0},
        )
    assert resp.status_code == 200
    assert resp.json() == {"count": 0, "items": []}


@pytest.mark.asyncio
async def test_query_missing_from_date_422(client):
    resp = await client.post(
        QUERY_URL, headers=_auth_header(), json={"filter": {}, "take": 0, "skip": 0}
    )
    assert resp.status_code == 422
    assert resp.json() == {"errorMessage": "Отсутствует обязательный атрибут fromDate"}


@pytest.mark.asyncio
async def test_query_returns_camel_case_items_and_forwards_paging(client):
    row = SimpleNamespace(
        id=uuid4(),
        mno_id=uuid4(),
        event_time=datetime(2025, 4, 25, 8, 48, 21, 280000, tzinfo=timezone.utc),
        is_empty=True,
        photo_link_before="http://a/before.jpg",
        photo_link_after="http://a/after.jpg",
        create_date=datetime(2025, 7, 9, 12, 39, 14, 605000, tzinfo=timezone.utc),
    )
    spy = AsyncMock(return_value=(1, [row]))
    with patch("app.utko.routers.events.service.query_truck_visit_events", new=spy):
        resp = await client.post(
            QUERY_URL,
            headers=_auth_header(),
            json={
                "filter": {
                    "fromDate": "2025-01-01T00:00:00Z",
                    "toDate": "2025-12-31T00:00:00Z",
                },
                "take": 10,
                "skip": 5,
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    item = body["items"][0]
    assert set(item) == {
        "id",
        "mnoId",
        "eventTime",
        "isEmpty",
        "photoLinkBefore",
        "photoLinkAfter",
        "createDate",
    }
    assert item["isEmpty"] is True
    assert item["eventTime"].endswith("Z")
    assert item["createDate"].endswith("Z")
    # take/skip и границы дат доехали до сервиса.
    kw = spy.call_args.kwargs
    assert kw["take"] == 10 and kw["skip"] == 5
    assert kw["from_date"].tzinfo is not None
    assert kw["to_date"] is not None


@pytest.mark.asyncio
async def test_query_take_capped_to_max(client):
    """take<=0 (в т.ч. по умолчанию) и слишком большой → MAX_TAKE: безлимита не бывает."""
    spy = AsyncMock(return_value=(0, []))
    with patch("app.utko.routers.events.service.query_truck_visit_events", new=spy):
        await client.post(
            QUERY_URL,
            headers=_auth_header(),
            json={"filter": {"fromDate": "2026-01-01T00:00:00Z"}, "take": 0},
        )
        assert spy.call_args.kwargs["take"] == utko_validate.MAX_TAKE
        await client.post(
            QUERY_URL,
            headers=_auth_header(),
            json={"filter": {"fromDate": "2026-01-01T00:00:00Z"}, "take": 10_000_000},
        )
        assert spy.call_args.kwargs["take"] == utko_validate.MAX_TAKE


# --- truck-visit-events/confirm --------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_missing_required_422(client):
    """Нет isEmptyConfirmed → 422 с точным текстом."""
    resp = await client.post(
        CONFIRM_URL,
        headers=_auth_header(),
        json=[{"eventId": str(uuid4())}],
    )
    assert resp.status_code == 422
    assert resp.json() == {
        "errorMessage": "Отсутствует обязательный атрибут isEmptyConfirmed"
    }


@pytest.mark.asyncio
async def test_confirm_unknown_event_422(client):
    with patch(
        "app.utko.routers.events.service.event_exists",
        new=AsyncMock(return_value=False),
    ):
        resp = await client.post(
            CONFIRM_URL,
            headers=_auth_header(),
            json=[{"eventId": str(uuid4()), "isEmptyConfirmed": True}],
        )
    assert resp.status_code == 422
    assert resp.json() == {"errorMessage": "Отсутствуют сведения о событии eventId"}


@pytest.mark.asyncio
async def test_confirm_bad_event_type_422(client):
    """eventType вне ФОТО-справочника → 422 «Свойство eventType имеет недопустимое значение»."""
    with patch(
        "app.utko.routers.events.service.event_exists",
        new=AsyncMock(return_value=True),
    ):
        resp = await client.post(
            CONFIRM_URL,
            headers=_auth_header(),
            json=[
                {
                    "eventId": str(uuid4()),
                    "isEmptyConfirmed": False,
                    "events": [{"eventType": 777}],
                }
            ],
        )
    assert resp.status_code == 422
    assert resp.json() == {"errorMessage": "Свойство eventType имеет недопустимое значение"}


@pytest.mark.asyncio
async def test_confirm_wrong_type_422(client):
    """isEmptyConfirmed не bool → 422 «Неверный тип данных …»."""
    resp = await client.post(
        CONFIRM_URL,
        headers=_auth_header(),
        json=[{"eventId": str(uuid4()), "isEmptyConfirmed": "yes"}],
    )
    assert resp.status_code == 422
    assert resp.json() == {"errorMessage": "Неверный тип данных у атрибута isEmptyConfirmed"}


@pytest.mark.asyncio
async def test_confirm_valid_saves(client):
    exists = AsyncMock(return_value=True)
    upsert = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    with patch("app.utko.routers.events.service.event_exists", new=exists), patch(
        "app.utko.routers.events.service.upsert_confirmation", new=upsert
    ):
        resp = await client.post(
            CONFIRM_URL,
            headers=_auth_header(),
            json=[
                {"eventId": str(uuid4()), "isEmptyConfirmed": True},
                {
                    "eventId": str(uuid4()),
                    "isEmptyConfirmed": False,
                    "problem": "мусор рядом",
                    "events": [{"eventType": 1, "typeContainer": 2}, {"eventType": 5}],
                },
            ],
        )
    assert resp.status_code == 200
    assert upsert.await_count == 2


@pytest.mark.asyncio
async def test_confirm_mixed_batch_all_or_nothing(client):
    """Смешанный батч [известный eventId, НЕизвестный] → 422, НИЧЕГО не сохранено (all-or-nothing)."""
    exists = AsyncMock(side_effect=[True, False])  # первый есть, второй — нет
    upsert = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    with patch("app.utko.routers.events.service.event_exists", new=exists), patch(
        "app.utko.routers.events.service.upsert_confirmation", new=upsert
    ):
        resp = await client.post(
            CONFIRM_URL,
            headers=_auth_header(),
            json=[
                {"eventId": str(uuid4()), "isEmptyConfirmed": True},
                {"eventId": str(uuid4()), "isEmptyConfirmed": False},
            ],
        )
    assert resp.status_code == 422
    assert resp.json() == {"errorMessage": "Отсутствуют сведения о событии eventId"}
    assert upsert.await_count == 0  # фаза сохранения не запускалась


@pytest.mark.asyncio
async def test_confirm_body_not_list_422(client):
    """Тело не JSON-массив (объект) → 422 «Неверный тип данных у атрибута body»."""
    resp = await client.post(
        CONFIRM_URL,
        headers=_auth_header(),
        json={"eventId": str(uuid4()), "isEmptyConfirmed": True},
    )
    assert resp.status_code == 422
    assert resp.json() == {"errorMessage": "Неверный тип данных у атрибута body"}


# --- video-events ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_video_unknown_mno_422(client):
    mno_id = str(uuid4())
    with patch(
        "app.utko.routers.events.service.mno_exists", new=AsyncMock(return_value=False)
    ):
        resp = await client.post(
            VIDEO_URL,
            headers=_auth_header(),
            json=[{"mnoId": mno_id, "eventTime": "2024-09-06T23:59:59Z"}],
        )
    assert resp.status_code == 422
    assert resp.json() == {
        "errorMessage": f"В БД ФГИС УТКО отсутствуют сведения МНО {mno_id}"
    }


@pytest.mark.asyncio
async def test_video_bad_event_type_422(client):
    """eventType=10 валиден для ФОТО, но НЕ для ВИДЕО → 422."""
    with patch(
        "app.utko.routers.events.service.mno_exists", new=AsyncMock(return_value=True)
    ):
        resp = await client.post(
            VIDEO_URL,
            headers=_auth_header(),
            json=[
                {
                    "mnoId": str(uuid4()),
                    "eventTime": "2024-09-06T23:59:59Z",
                    "events": [{"eventType": 10}],
                }
            ],
        )
    assert resp.status_code == 422
    assert resp.json() == {"errorMessage": "Свойство eventType имеет недопустимое значение"}


@pytest.mark.asyncio
async def test_video_one_bad_element_rejects_whole_batch(client):
    """Второй элемент с битым eventTime → весь пакет отклонён, save НЕ вызван."""
    save = AsyncMock()
    with patch(
        "app.utko.routers.events.service.mno_exists", new=AsyncMock(return_value=True)
    ), patch("app.utko.routers.events.service.save_video_event", new=save):
        resp = await client.post(
            VIDEO_URL,
            headers=_auth_header(),
            json=[
                {"mnoId": str(uuid4()), "eventTime": "2024-09-06T23:59:59Z"},
                {"mnoId": str(uuid4()), "eventTime": "не-дата"},
            ],
        )
    assert resp.status_code == 422
    assert save.await_count == 0


@pytest.mark.asyncio
async def test_video_valid_returns_uuids(client):
    generated = [uuid4(), uuid4()]

    async def _save(session, item):
        return SimpleNamespace(id=generated.pop(0))

    ext1 = str(uuid4())
    with patch(
        "app.utko.routers.events.service.mno_exists", new=AsyncMock(return_value=True)
    ), patch("app.utko.routers.events.service.save_video_event", new=_save):
        resp = await client.post(
            VIDEO_URL,
            headers=_auth_header(),
            json=[
                {
                    "mnoId": str(uuid4()),
                    "externalEventId": ext1,
                    "eventTime": "2024-09-06T23:59:59Z",
                    "photoLink": "https://x/y.jpg",
                    "events": [{"eventType": 1, "typeContainer": 2}],
                },
                {
                    "mnoId": str(uuid4()),
                    "eventTime": "2024-08-07T23:59:59Z",
                    "events": [{"eventType": 98}],
                },
            ],
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["externalEventId"] == ext1
    assert body[0]["videoEventUuid"]
    # Второй элемент без externalEventId → null, но videoEventUuid есть.
    assert body[1]["externalEventId"] is None
    assert body[1]["videoEventUuid"]


@pytest.mark.asyncio
async def test_video_external_event_id_non_uuid_echoed(client):
    """externalEventId — произвольная строка «123» (не UUID) принимается и возвращается verbatim."""

    async def _save(session, item):
        # сервис получает строку как есть
        assert item["external_event_id"] == "123"
        return SimpleNamespace(id=uuid4())

    with patch(
        "app.utko.routers.events.service.mno_exists", new=AsyncMock(return_value=True)
    ), patch("app.utko.routers.events.service.save_video_event", new=_save):
        resp = await client.post(
            VIDEO_URL,
            headers=_auth_header(),
            json=[
                {
                    "mnoId": str(uuid4()),
                    "externalEventId": "123",
                    "eventTime": "2024-09-06T23:59:59Z",
                }
            ],
        )
    assert resp.status_code == 200
    assert resp.json()[0]["externalEventId"] == "123"


@pytest.mark.asyncio
async def test_video_external_event_id_non_string_422(client):
    """externalEventId не строка (число) → 422 «Неверный тип данных …»."""
    with patch(
        "app.utko.routers.events.service.mno_exists", new=AsyncMock(return_value=True)
    ):
        resp = await client.post(
            VIDEO_URL,
            headers=_auth_header(),
            json=[
                {
                    "mnoId": str(uuid4()),
                    "externalEventId": 123,
                    "eventTime": "2024-09-06T23:59:59Z",
                }
            ],
        )
    assert resp.status_code == 422
    assert resp.json() == {
        "errorMessage": "Неверный тип данных у атрибута externalEventId"
    }


@pytest.mark.asyncio
async def test_video_body_not_list_422(client):
    """Тело video-events не JSON-массив → 422 «Неверный тип данных у атрибута body»."""
    resp = await client.post(
        VIDEO_URL,
        headers=_auth_header(),
        json={"mnoId": str(uuid4()), "eventTime": "2024-09-06T23:59:59Z"},
    )
    assert resp.status_code == 422
    assert resp.json() == {"errorMessage": "Неверный тип данных у атрибута body"}
