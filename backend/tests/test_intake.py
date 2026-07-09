"""Тесты публичного приёма Яндекс-Формы (/api/v1/intake/yandex) — офлайн.

Сервис create_incident_from_form мокается на границе роута; разбор параметров
проверяется отдельным прямым вызовом сервиса (без БД).
"""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from PIL import Image

from app.config import settings
from app.models import Incident, Mno
from app.schemas.mno import MnoVolunteerCreate
from app.services import intake as intake_svc
from app.services import mno as mno_service
from app.services.intake import (
    _deg2num,
    _pick_zoom,
    create_incident_from_form,
    create_incident_from_max,
    create_incident_from_max_selected,
    create_incident_from_public_form,
    prepare_max_report,
)


def _jpeg_bytes(size=(1200, 900), color=(0, 120, 0)) -> bytes:
    """Реальный JPEG, сгенерированный Pillow.

    Сырой стаб \\xff\\xd8\\xff Pillow открыть не может — фото теперь
    пере-кодируются через Pillow, поэтому нужен настоящий декодируемый файл.
    """
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


# Валидный JPEG (декодируется Pillow) — для случаев, где важно лишь количество.
_FAKE_IMG = _jpeg_bytes()
# Содержимое, не являющееся изображением (Pillow не откроет → отбраковка 400).
_NOT_IMAGE = b"not an image"


class _FakeUpload:
    """Минимальный UploadFile-подобный объект: async read + filename/content_type."""

    def __init__(self, data: bytes, filename: str = "0.jpg", content_type: str = "image/jpeg"):
        self._buf = BytesIO(data)
        self.filename = filename
        self.content_type = content_type

    async def read(self, size: int = -1) -> bytes:
        return self._buf.read(size)

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


# --------------------------------------------------------------------------- #
# Публичная форма волонтёра: GET /suggest/address                              #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_suggest_address_empty_token_returns_empty(monkeypatch):
    """Без DADATA_API_KEY сервис подсказок отдаёт [] (graceful, прямой вызов)."""
    from app.services import dadata as dadata_service

    monkeypatch.setattr(settings, "DADATA_API_KEY", None)
    assert await dadata_service.suggest_address("Самара улица") == []


@pytest.mark.asyncio
async def test_suggest_address_short_query_returns_empty(monkeypatch):
    """Запрос короче 3 символов → [] даже при заданном ключе."""
    from app.services import dadata as dadata_service

    monkeypatch.setattr(settings, "DADATA_API_KEY", "key")
    assert await dadata_service.suggest_address("ab") == []


# --------------------------------------------------------------------------- #
# geocode_address — бесплатный геокод через Подсказки (suggest top-hit)        #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_geocode_address_top_hit_includes_house():
    """geocode_address берёт ТОП-подсказку: улица склеивается с домом, coords проброшены."""
    from app.services import dadata as dadata_service

    top = {
        "value": "г Самара, Виноградный пер, д 6А",
        "region": "Самарская обл",
        "city": "г Самара",
        "street": "Виноградный переулок",
        "house": "6А",
        "coords": "53.20, 50.15",
        "geo_lat": "53.20",
        "geo_lon": "50.15",
    }
    # Мокаем suggest_address — реальная сеть НЕ дёргается.
    with patch(
        "app.services.dadata.suggest_address", new=AsyncMock(return_value=[top])
    ) as fake_suggest:
        result = await dadata_service.geocode_address("Самара Виноградный 6А")

    assert result == {
        "region": "Самарская обл",
        "city": "г Самара",
        "street": "Виноградный переулок, 6А",  # дом НЕ потерян
        "coords": "53.20, 50.15",
        "geo_lat": "53.20",
        "geo_lon": "50.15",
    }
    # Запрашиваем только одну (топовую) подсказку.
    fake_suggest.assert_awaited_once()
    assert fake_suggest.await_args.kwargs.get("count") == 1


@pytest.mark.asyncio
async def test_geocode_address_no_suggestions_returns_none():
    """suggest_address → [] → geocode_address возвращает None (graceful)."""
    from app.services import dadata as dadata_service

    with patch(
        "app.services.dadata.suggest_address", new=AsyncMock(return_value=[])
    ):
        assert await dadata_service.geocode_address("ничего похожего") is None


@pytest.mark.asyncio
async def test_geocode_address_house_only_keeps_number():
    """Только дом без улицы (street пуст) → street = номер дома (дом не теряется)."""
    from app.services import dadata as dadata_service

    top = {
        "region": "Самарская обл",
        "city": "г Самара",
        "street": "",
        "house": "10",
        "coords": "53.0, 50.0",
        "geo_lat": "53.0",
        "geo_lon": "50.0",
    }
    with patch(
        "app.services.dadata.suggest_address", new=AsyncMock(return_value=[top])
    ):
        result = await dadata_service.geocode_address("Самара дом 10")

    assert result["street"] == "10"
    assert result["coords"] == "53.0, 50.0"


@pytest.mark.asyncio
async def test_geocode_address_no_key_no_network(monkeypatch):
    """Без DADATA_API_KEY suggest отдаёт [] ДО httpx → geocode None, сеть не трогается."""
    from app.services import dadata as dadata_service

    monkeypatch.setattr(settings, "DADATA_API_KEY", None)
    assert await dadata_service.geocode_address("Самара, улица 1") is None


@pytest.mark.asyncio
async def test_suggest_address_route_too_short(client):
    """GET /suggest/address с q<3 → {"suggestions": []}, DaData не вызывается."""
    resp = await client.get("/api/v1/intake/suggest/address", params={"q": "ab"})
    assert resp.status_code == 200
    assert resp.json() == {"suggestions": []}


@pytest.mark.asyncio
async def test_suggest_address_route_returns_suggestions(client):
    """GET /suggest/address проксирует результат сервиса DaData в конверт."""
    sample = [
        {
            "value": "г Самара, ул Ленина, д 1",
            "region": "Самарская обл",
            "city": "г Самара",
            "street": "ул Ленина",
            "coords": "53.2, 50.1",
            "geo_lat": "53.2",
            "geo_lon": "50.1",
        }
    ]
    fake = AsyncMock(return_value=sample)
    with patch("app.api.v1.intake.dadata_service.suggest_address", new=fake):
        resp = await client.get(
            "/api/v1/intake/suggest/address",
            params={"q": "Самара Ленина", "count": 5},
        )
    assert resp.status_code == 200
    assert resp.json() == {"suggestions": sample}
    fake.assert_awaited_once()


def _suggest_call(fake):
    """Достаёт позиционные/именованные аргументы вызова мокнутого suggest_address.

    Сигнатура сервиса: suggest_address(q, count, from_bound, to_bound, locations).
    Возвращает (from_bound, to_bound, locations) независимо от позиц./kwargs.
    """
    args = fake.call_args.args
    kwargs = fake.call_args.kwargs
    from_bound = args[2] if len(args) > 2 else kwargs.get("from_bound")
    to_bound = args[3] if len(args) > 3 else kwargs.get("to_bound")
    locations = args[4] if len(args) > 4 else kwargs.get("locations")
    return from_bound, to_bound, locations


@pytest.mark.asyncio
async def test_suggest_address_kind_region_bounds(client):
    """kind=region → from_bound/to_bound='region', locations не передаются."""
    fake = AsyncMock(return_value=[])
    with patch("app.api.v1.intake.dadata_service.suggest_address", new=fake):
        resp = await client.get(
            "/api/v1/intake/suggest/address",
            params={"q": "Самар", "kind": "region"},
        )
    assert resp.status_code == 200
    from_bound, to_bound, locations = _suggest_call(fake)
    assert from_bound == "region"
    assert to_bound == "region"
    assert locations is None


@pytest.mark.asyncio
async def test_suggest_address_kind_city_with_region_locations(client):
    """kind=city&region=X → from_bound=city/to_bound=settlement, locations=[{region:X}]."""
    fake = AsyncMock(return_value=[])
    with patch("app.api.v1.intake.dadata_service.suggest_address", new=fake):
        resp = await client.get(
            "/api/v1/intake/suggest/address",
            params={"q": "Кинель", "kind": "city", "region": "Самарская область"},
        )
    assert resp.status_code == 200
    from_bound, to_bound, locations = _suggest_call(fake)
    assert from_bound == "city"
    assert to_bound == "settlement"
    assert locations == [{"region": "Самарская область"}]


@pytest.mark.asyncio
async def test_suggest_address_kind_city_without_region_no_locations(client):
    """kind=city без region → locations не строятся (None)."""
    fake = AsyncMock(return_value=[])
    with patch("app.api.v1.intake.dadata_service.suggest_address", new=fake):
        resp = await client.get(
            "/api/v1/intake/suggest/address",
            params={"q": "Кинель", "kind": "city"},
        )
    assert resp.status_code == 200
    from_bound, to_bound, locations = _suggest_call(fake)
    assert from_bound == "city"
    assert to_bound == "settlement"
    assert locations is None


@pytest.mark.asyncio
async def test_suggest_address_kind_street_with_region_and_city(client):
    """kind=street&region=X&city=Y → bounds street/house, locations с region+city."""
    fake = AsyncMock(return_value=[])
    with patch("app.api.v1.intake.dadata_service.suggest_address", new=fake):
        resp = await client.get(
            "/api/v1/intake/suggest/address",
            params={
                "q": "Маяковского",
                "kind": "street",
                "region": "Самарская область",
                "city": "г. Кинель",
            },
        )
    assert resp.status_code == 200
    from_bound, to_bound, locations = _suggest_call(fake)
    assert from_bound == "street"
    assert to_bound == "house"
    assert locations == [{"region": "Самарская область", "city": "г. Кинель"}]


@pytest.mark.asyncio
async def test_suggest_address_default_kind_no_bounds(client):
    """kind по умолчанию (full) → bounds/locations не передаются (None)."""
    fake = AsyncMock(return_value=[])
    with patch("app.api.v1.intake.dadata_service.suggest_address", new=fake):
        resp = await client.get(
            "/api/v1/intake/suggest/address",
            params={"q": "Самара Ленина"},
        )
    assert resp.status_code == 200
    from_bound, to_bound, locations = _suggest_call(fake)
    assert from_bound is None
    assert to_bound is None
    assert locations is None


# --------------------------------------------------------------------------- #
# Публичная карта формы: GET /mno-points                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_mno_points_public_returns_points(client):
    """GET /intake/mno-points публичный (без auth) → points/total/capped; bbox проброшен."""
    from app.schemas.mno import MnoFormPoint, MnoFormPointsResponse

    resp_obj = MnoFormPointsResponse(
        points=[
            MnoFormPoint(
                id=uuid4(),
                coords="53.231410, 50.166820",
                reg="63-04-001162",
                address="Бульварная улица, 18",
                name="Площадка A",
            )
        ],
        total=1,
        capped=False,
    )
    spy = AsyncMock(return_value=resp_obj)
    with patch("app.api.v1.intake.mno_service.list_form_points", new=spy):
        resp = await client.get(
            "/api/v1/intake/mno-points", params={"bbox": "53.0,50.0,54.0,51.0"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["capped"] is False
    assert len(body["points"]) == 1
    point = body["points"][0]
    assert point["reg"] == "63-04-001162"
    assert point["address"] == "Бульварная улица, 18"
    assert point["name"] == "Площадка A"
    assert point["coords"] == "53.231410, 50.166820"
    # bbox проброшен в сервис.
    assert spy.call_args.kwargs["bbox"] == "53.0,50.0,54.0,51.0"


@pytest.mark.asyncio
async def test_mno_points_public_no_bbox_empty(client):
    """Без bbox эндпоинт 200 с пустым списком — сервис решает не тянуть весь реестр."""
    from app.schemas.mno import MnoFormPointsResponse

    spy = AsyncMock(
        return_value=MnoFormPointsResponse(points=[], total=0, capped=False)
    )
    with patch("app.api.v1.intake.mno_service.list_form_points", new=spy):
        resp = await client.get("/api/v1/intake/mno-points")
    assert resp.status_code == 200
    assert resp.json() == {"points": [], "total": 0, "capped": False}
    # bbox по умолчанию "" проброшен в сервис.
    assert spy.call_args.kwargs["bbox"] == ""


# --------------------------------------------------------------------------- #
# Публичное добавление МНО волонтёром: POST /intake/mno                         #
# --------------------------------------------------------------------------- #


def _volunteer_detail(**kw):
    """MnoDetail волонтёрского МНО (source='volunteer') для мока сервиса."""
    from app.schemas.mno import MnoDetail

    base = dict(
        id=uuid4(),
        reg="",
        name="Площадка волонтёра",
        region_code="63",
        region_name="Самарская область",
        city="г. Самара",
        address="ул. Ленина, 1",
        coords="53.2, 50.6",
        source="volunteer",
        fgis_id=None,
        synced=False,
        sync_date=None,
        incidents=0,
    )
    base.update(kw)
    return MnoDetail(**base)


@pytest.mark.asyncio
async def test_public_mno_creates_volunteer(client):
    """POST /intake/mno публичный, multipart (БЕЗ токена) → 200; сервис вызван, source='volunteer'."""
    created = _volunteer_detail()
    spy = AsyncMock(return_value=created)
    with patch(
        "app.api.v1.intake.mno_service.create_mno_from_volunteer", new=spy
    ):
        resp = await client.post(
            "/api/v1/intake/mno",
            data={
                "name": "Площадка волонтёра",
                "region_code": "63",
                "city": "г. Самара",
                "address": "ул. Ленина, 1",
                "coords": "53.2, 50.6",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "volunteer"
    assert body["synced"] is False
    assert body["fgis_id"] is None
    assert body["id"] == str(created.id)
    # Тело передано в сервис как MnoVolunteerCreate (2-й позиционный аргумент).
    spy.assert_awaited_once()
    payload = spy.call_args.args[1]
    assert payload.address == "ул. Ленина, 1"
    assert payload.coords == "53.2, 50.6"


@pytest.mark.asyncio
async def test_public_mno_passes_comment_and_photos(client):
    """multipart с comment + файлом фото → сервис получает comment и photo_files."""
    created = _volunteer_detail(comment="бак переполнен")
    spy = AsyncMock(return_value=created)
    with patch(
        "app.api.v1.intake.mno_service.create_mno_from_volunteer", new=spy
    ):
        resp = await client.post(
            "/api/v1/intake/mno",
            data={
                "address": "ул. Ленина, 1",
                "coords": "53.2, 50.6",
                "comment": "бак переполнен",
            },
            files=[("photos", ("0.jpg", BytesIO(_FAKE_IMG), "image/jpeg"))],
        )
    assert resp.status_code == 200
    assert resp.json()["comment"] == "бак переполнен"
    spy.assert_awaited_once()
    # comment пробрасывается в модель, фото — отдельным kwarg photo_files.
    assert spy.call_args.args[1].comment == "бак переполнен"
    photo_files = spy.call_args.kwargs["photo_files"]
    assert len(photo_files) == 1


@pytest.mark.asyncio
async def test_public_mno_honeypot_drops(client):
    """Заполненный honeypot website → 200 ok, но сервис НЕ вызывается."""
    spy = AsyncMock()
    with patch(
        "app.api.v1.intake.mno_service.create_mno_from_volunteer", new=spy
    ):
        resp = await client.post(
            "/api/v1/intake/mno",
            data={
                "address": "ул. Ленина, 1",
                "coords": "53.2, 50.6",
                "website": "http://spam.example",
            },
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    spy.assert_not_awaited()


@pytest.mark.asyncio
async def test_public_mno_requires_address_and_coords(client):
    """Пустые address/coords → 400 VALIDATION_ERROR (реальный сервис, до записи в БД)."""
    resp = await client.post(
        "/api/v1/intake/mno", data={"address": "", "coords": ""}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def _mno_volunteer_session():
    """Fake session для сервис-теста МНО: add копит, flush присваивает Mno.id, execute → регионы."""
    added: list = []
    session = AsyncMock()
    session.add = MagicMock(side_effect=added.append)

    async def _flush():
        for o in added:
            if isinstance(o, Mno) and getattr(o, "id", None) is None:
                o.id = uuid4()

    session.flush = AsyncMock(side_effect=_flush)
    names_res = MagicMock()
    names_res.all.return_value = [("63", "Самарская область")]
    session.execute = AsyncMock(return_value=names_res)
    return session, added


@pytest.mark.asyncio
async def test_volunteer_mno_stores_photos_and_comment(monkeypatch, tmp_path):
    """Сервис: фото волонтёрского МНО сохраняются в {STORAGE_DIR}/mno/{id}/ (FULL+THUMB),
    photo_urls указывают на /mno-photo/, comment проброшен в карточку."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    session, added = _mno_volunteer_session()
    data = MnoVolunteerCreate(
        address="ул. Ленина, 1", coords="53.2, 50.6", comment="переполнен бак"
    )
    detail = await mno_service.create_mno_from_volunteer(
        session,
        data,
        photo_files=[_FakeUpload(_jpeg_bytes(), filename="orig.png", content_type="image/png")],
    )

    created = next(o for o in added if isinstance(o, Mno))
    mno_dir = tmp_path / "mno" / str(created.id)
    assert (mno_dir / "0.jpg").is_file()
    assert (mno_dir / "0_thumb.jpg").is_file()
    assert detail.photo_urls == [f"/api/v1/intake/mno-photo/{created.id}/0.jpg"]
    assert detail.comment == "переполнен бак"


@pytest.mark.asyncio
async def test_mno_photo_route_serves_and_antitraversal(client, monkeypatch, tmp_path):
    """GET /intake/mno-photo/{id}/{file}: отдаёт JPEG; битый filename / не-UUID → 404."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    mid = str(uuid4())
    mno_dir = tmp_path / "mno" / mid
    mno_dir.mkdir(parents=True)
    (mno_dir / "0.jpg").write_bytes(_jpeg_bytes())

    ok = await client.get(f"/api/v1/intake/mno-photo/{mid}/0.jpg")
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "image/jpeg"
    assert ok.headers["x-content-type-options"] == "nosniff"
    # битый filename (не по паттерну) → 404
    bad = await client.get(f"/api/v1/intake/mno-photo/{mid}/evil.txt")
    assert bad.status_code == 404
    # не-UUID mno_id → 404
    notuuid = await client.get("/api/v1/intake/mno-photo/not-a-uuid/0.jpg")
    assert notuuid.status_code == 404


# --------------------------------------------------------------------------- #
# Публичная форма волонтёра: POST /form                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_public_form_creates_incident(client):
    """POST /form с 1 фото → 200 ok + incident_id; сервис вызван с source-полями."""
    fake_incident = Incident(source="form", status="new")
    fake_incident.id = uuid4()
    create = AsyncMock(return_value=fake_incident)
    quote = AsyncMock(return_value="«тестовая цитата» — Тест Автор")

    with patch(
        "app.api.v1.intake.intake_service.create_incident_from_public_form",
        new=create,
    ), patch("app.api.v1.intake.quotes_service.nature_quote", new=quote):
        resp = await client.post(
            "/api/v1/intake/form",
            data={
                "fio": "Иванов Иван",
                "full_address": "Самарская область, г. Самара, ул. Ленина, 1",
                "region": "Самарская область",
                "city": "г. Самара",
                "street": "ул. Ленина, 1",
                "coords": "53.2, 50.1",
                "incident_type": "fire",
                "comment": "Баки переполнены",
                "photo_time": "2026-04-26T08:05:00",
                "bins": "yes",
                "website": "",
            },
            files=[("photos", ("0.jpg", BytesIO(_FAKE_IMG), "image/jpeg"))],
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["incident_id"] == str(fake_incident.id)
    assert body["quote"] == "«тестовая цитата» — Тест Автор"
    # Цитата сохранена на самом инциденте (2-й commit в роуте).
    assert fake_incident.quote == "«тестовая цитата» — Тест Автор"

    create.assert_awaited_once()
    kwargs = create.call_args.kwargs
    assert kwargs["fio"] == "Иванов Иван"
    assert kwargs["region"] == "Самарская область"
    # Роут прокидывает новые Form-поля в сервис.
    assert kwargs["incident_type"] == "fire"
    assert kwargs["comment"] == "Баки переполнены"
    assert len(kwargs["photo_files"]) == 1


@pytest.mark.asyncio
async def test_public_form_forwards_mno_reg(client):
    """POST /form прокидывает mno_reg (рег-номер выбранного на карте МНО) в сервис."""
    fake_incident = Incident(source="form", status="new")
    fake_incident.id = uuid4()
    create = AsyncMock(return_value=fake_incident)
    quote = AsyncMock(return_value="«ц» — А")
    with patch(
        "app.api.v1.intake.intake_service.create_incident_from_public_form",
        new=create,
    ), patch("app.api.v1.intake.quotes_service.nature_quote", new=quote):
        resp = await client.post(
            "/api/v1/intake/form",
            data={
                "fio": "Волонтёр",
                "region": "Самарская область",
                "city": "г. Самара",
                "street": "Бульварная улица, 18",
                "coords": "53.231410, 50.166820",
                "mno_reg": "63-04-001162",
                "website": "",
            },
        )
    assert resp.status_code == 200
    create.assert_awaited_once()
    assert create.call_args.kwargs["mno_reg"] == "63-04-001162"


@pytest.mark.asyncio
async def test_public_form_forwards_mno_id(client):
    """POST /form прокидывает mno_id (id выбранного на карте МНО) в сервис."""
    fake_incident = Incident(source="form", status="new")
    fake_incident.id = uuid4()
    mno_id = str(uuid4())
    create = AsyncMock(return_value=fake_incident)
    quote = AsyncMock(return_value="«ц» — А")
    with patch(
        "app.api.v1.intake.intake_service.create_incident_from_public_form",
        new=create,
    ), patch("app.api.v1.intake.quotes_service.nature_quote", new=quote):
        resp = await client.post(
            "/api/v1/intake/form",
            data={
                "fio": "Волонтёр",
                "region": "Самарская область",
                "city": "г. Самара",
                "street": "Бульварная улица, 18",
                "coords": "53.231410, 50.166820",
                "mno_reg": "63-04-001162",
                "mno_id": mno_id,
                "website": "",
            },
        )
    assert resp.status_code == 200
    create.assert_awaited_once()
    assert create.call_args.kwargs["mno_id"] == mno_id


@pytest.mark.asyncio
async def test_public_form_honeypot_drops(client):
    """Заполненный honeypot website → 200 ok, но сервис НЕ вызывается."""
    create = AsyncMock()
    with patch(
        "app.api.v1.intake.intake_service.create_incident_from_public_form",
        new=create,
    ):
        resp = await client.post(
            "/api/v1/intake/form",
            data={"fio": "Бот", "website": "http://spam.example"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_public_form_too_many_photos_400(client):
    """>6 фото → 400 VALIDATION_ERROR (реальный сервис, проверка до записи БД)."""
    files = [
        ("photos", (f"{i}.jpg", BytesIO(_FAKE_IMG), "image/jpeg")) for i in range(7)
    ]
    resp = await client.post(
        "/api/v1/intake/form",
        data={"fio": "Много фото"},
        files=files,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_public_form_bad_content_type_400(client):
    """Недопустимый content-type фото → 400 VALIDATION_ERROR."""
    resp = await client.post(
        "/api/v1/intake/form",
        data={"fio": "Плохой файл"},
        files=[("photos", ("note.txt", BytesIO(b"hello"), "text/plain"))],
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_public_form_fake_signature_rejected_400(client):
    """Не-картинка с content_type=image/jpeg → 400 (проверка по магическим байтам)."""
    resp = await client.post(
        "/api/v1/intake/form",
        data={"fio": "Подделка"},
        files=[("photos", ("evil.jpg", BytesIO(_NOT_IMAGE), "image/jpeg"))],
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_public_form_resizes_and_serves(client, fake_session, monkeypatch, tmp_path):
    """E2E через роут: POST /form с 1 фото → на диске FULL+THUMB; оба отдаются 200
    с image/jpeg + nosniff; thumb ≤400px и меньше full."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    # Имитируем server_default id (gen_random_uuid): flush присваивает UUID.
    added: list = []
    fake_session.add = MagicMock(side_effect=added.append)

    async def _flush(*args, **kwargs):
        for obj in added:
            if isinstance(obj, Incident) and getattr(obj, "id", None) is None:
                obj.id = uuid4()

    fake_session.flush = AsyncMock(side_effect=_flush)
    monkeypatch.setattr(
        "app.api.v1.intake.quotes_service.nature_quote",
        AsyncMock(return_value="«цитата» — Автор"),
    )

    resp = await client.post(
        "/api/v1/intake/form",
        data={"fio": "Фото"},
        files=[("photos", ("orig.png", BytesIO(_jpeg_bytes()), "image/png"))],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    incident_id = body["incident_id"]

    incident_dir = tmp_path / "incidents" / incident_id
    assert (incident_dir / "0.jpg").is_file()
    assert (incident_dir / "0_thumb.jpg").is_file()

    full_resp = await client.get(f"/api/v1/intake/photo/{incident_id}/0.jpg")
    thumb_resp = await client.get(f"/api/v1/intake/photo/{incident_id}/0_thumb.jpg")
    assert full_resp.status_code == 200
    assert thumb_resp.status_code == 200
    assert full_resp.headers["content-type"] == "image/jpeg"
    assert thumb_resp.headers["x-content-type-options"] == "nosniff"

    with Image.open(BytesIO(full_resp.content)) as f_img, Image.open(
        BytesIO(thumb_resp.content)
    ) as t_img:
        assert max(t_img.size) <= 400
        assert max(t_img.size) < max(f_img.size)


# --------------------------------------------------------------------------- #
# Авторство волонтёра: опциональный volunteer-токен → volunteer_id на приёме    #
# --------------------------------------------------------------------------- #


def _fake_volunteer():
    """Фейковый активный волонтёр с известным id (для override get_optional_volunteer)."""
    from app.models import Volunteer

    v = Volunteer(email="author@example.com", password_hash="x", is_active=True)
    v.id = uuid4()
    return v


@pytest.mark.asyncio
async def test_public_form_attributes_volunteer(client):
    """POST /form с валидным volunteer-токеном (override get_optional_volunteer) →
    сервис получает volunteer_id автора (отчёт попадёт в «Мои отчёты» приложения)."""
    from app.deps import get_optional_volunteer
    from app.main import app

    fake_vol = _fake_volunteer()
    app.dependency_overrides[get_optional_volunteer] = lambda: fake_vol

    fake_incident = Incident(source="form", status="new")
    fake_incident.id = uuid4()
    create = AsyncMock(return_value=fake_incident)
    quote = AsyncMock(return_value="«ц» — А")
    try:
        with patch(
            "app.api.v1.intake.intake_service.create_incident_from_public_form",
            new=create,
        ), patch("app.api.v1.intake.quotes_service.nature_quote", new=quote):
            resp = await client.post(
                "/api/v1/intake/form", data={"fio": "Волонтёр", "website": ""}
            )
    finally:
        app.dependency_overrides.pop(get_optional_volunteer, None)

    assert resp.status_code == 200
    create.assert_awaited_once()
    assert create.call_args.kwargs["volunteer_id"] == fake_vol.id


@pytest.mark.asyncio
async def test_public_form_anonymous_volunteer_id_none(client):
    """POST /form БЕЗ токена (аноним/веб-форма) → сервис получает volunteer_id=None."""
    fake_incident = Incident(source="form", status="new")
    fake_incident.id = uuid4()
    create = AsyncMock(return_value=fake_incident)
    quote = AsyncMock(return_value="«ц» — А")
    with patch(
        "app.api.v1.intake.intake_service.create_incident_from_public_form",
        new=create,
    ), patch("app.api.v1.intake.quotes_service.nature_quote", new=quote):
        resp = await client.post(
            "/api/v1/intake/form", data={"fio": "Аноним", "website": ""}
        )
    assert resp.status_code == 200
    create.assert_awaited_once()
    assert create.call_args.kwargs["volunteer_id"] is None


@pytest.mark.asyncio
async def test_public_mno_attributes_volunteer(client):
    """POST /intake/mno с валидным volunteer-токеном → сервис получает volunteer_id автора."""
    from app.deps import get_optional_volunteer
    from app.main import app

    fake_vol = _fake_volunteer()
    app.dependency_overrides[get_optional_volunteer] = lambda: fake_vol

    spy = AsyncMock(return_value=_volunteer_detail())
    try:
        with patch(
            "app.api.v1.intake.mno_service.create_mno_from_volunteer", new=spy
        ):
            resp = await client.post(
                "/api/v1/intake/mno",
                data={"address": "ул. Ленина, 1", "coords": "53.2, 50.6"},
            )
    finally:
        app.dependency_overrides.pop(get_optional_volunteer, None)

    assert resp.status_code == 200
    spy.assert_awaited_once()
    assert spy.call_args.kwargs["volunteer_id"] == fake_vol.id


@pytest.mark.asyncio
async def test_public_mno_anonymous_volunteer_id_none(client):
    """POST /intake/mno БЕЗ токена (аноним) → сервис получает volunteer_id=None."""
    spy = AsyncMock(return_value=_volunteer_detail())
    with patch(
        "app.api.v1.intake.mno_service.create_mno_from_volunteer", new=spy
    ):
        resp = await client.post(
            "/api/v1/intake/mno",
            data={"address": "ул. Ленина, 1", "coords": "53.2, 50.6"},
        )
    assert resp.status_code == 200
    spy.assert_awaited_once()
    assert spy.call_args.kwargs["volunteer_id"] is None


# --------------------------------------------------------------------------- #
# create_incident_from_public_form — ветвление адреса/баков (без диска/БД)     #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_public_service_uses_explicit_address(fake_session):
    """Явные region/city/street имеют приоритет над разбором full_address."""
    fake_session.add = MagicMock()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="Пётр",
        full_address="игнор, игнор, игнор",
        region="Самарская область",
        city="г. Самара",
        street="ул. Мира, 5",
        coords="53.1, 50.2",
        photo_time="2026-04-26T08:05:00",
        bins="no",
        photo_files=[],
    )
    assert incident.source == "form"  # без volunteer_id — анонимная веб-форма
    assert incident.region == "Самарская область"
    assert incident.city == "г. Самара"
    assert incident.street == "ул. Мира, 5"
    assert incident.bins is False
    assert incident.photo_time is not None and incident.photo_time.tzinfo is not None
    assert incident.photos == 0
    assert incident.photo_urls == []


@pytest.mark.asyncio
async def test_public_service_volunteer_token_sets_source_app(fake_session):
    """С volunteer_id (мобильное приложение) source='app'; volunteer_id пишется в инцидент."""
    fake_session.add = MagicMock()
    vol_id = uuid4()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="Волонтёр",
        full_address="Самарская область, г. Самара, ул. Мира, 5",
        region="Самарская область",
        city="г. Самара",
        street="ул. Мира, 5",
        coords="53.1, 50.2",
        photo_time="",
        bins="",
        photo_files=[],
        volunteer_id=vol_id,
    )
    assert incident.source == "app"
    assert incident.volunteer_id == vol_id


@pytest.mark.asyncio
async def test_public_service_derives_address_when_empty(fake_session):
    """Пустые region/city/street → разбор из full_address эвристикой."""
    fake_session.add = MagicMock()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="",
        full_address="Самарская область, г. Кинель, ул. Маяковского, 41",
        region="",
        city="",
        street="",
        coords="",
        photo_time="",
        bins="",
        photo_files=[],
    )
    assert incident.region == "Самарская область"
    assert incident.city == "г. Кинель"
    assert incident.street == "ул. Маяковского, 41"
    assert incident.bins is None
    assert incident.photo_time is None


@pytest.mark.asyncio
async def test_public_service_backfills_address_from_mno(fake_session):
    """Выбран mno_id, адрес пуст → регион/город/адрес/координаты/mno_reg берутся из МНО.

    Мобильное приложение шлёт только mno_id (адрес живёт на площадке) — отчёт не должен
    остаться с пустыми region/city/street/coords (иначе «Мои отчёты» без адреса)."""
    mid = uuid4()
    mno = Mno(
        reg="63-04-001162",
        name="Контейнерная площадка",
        region_code="63",
        city="г. Самара",
        address="ул. Ленина, 1",
        coords="53.2, 50.6",
    )
    mno.id = mid
    # 1-й execute → сам МНО (select Mno); 2-й → имя региона по region_code (select Region.name).
    res_mno = MagicMock()
    res_mno.scalar_one_or_none.return_value = mno
    res_region = MagicMock()
    res_region.scalar_one_or_none.return_value = "Самарская область"
    fake_session.execute = AsyncMock(side_effect=[res_mno, res_region])
    fake_session.add = MagicMock()

    incident = await create_incident_from_public_form(
        fake_session,
        fio="",
        full_address="",
        region="",
        city="",
        street="",
        coords="",
        photo_time="",
        bins="",
        photo_files=[],
        mno_id=str(mid),
    )
    assert incident.mno_id == mid
    assert incident.region == "Самарская область"
    assert incident.city == "г. Самара"
    assert incident.street == "ул. Ленина, 1"
    assert incident.coords == "53.2, 50.6"
    assert incident.mno_reg == "63-04-001162"
    # координаты МНО распарсились в числовые lat/lon (bbox-фильтр карты).
    assert incident.lat == 53.2 and incident.lon == 50.6


@pytest.mark.asyncio
async def test_public_service_mno_does_not_override_explicit_address(fake_session):
    """Явный адрес с формы приоритетнее МНО; но пустой mno_reg подтягивается из МНО."""
    mid = uuid4()
    mno = Mno(
        reg="63-04-777",
        name="П",
        region_code="63",
        city="МНО-город",
        address="МНО-адрес",
        coords="1, 1",
    )
    mno.id = mid
    res_mno = MagicMock()
    res_mno.scalar_one_or_none.return_value = mno
    fake_session.execute = AsyncMock(return_value=res_mno)
    fake_session.add = MagicMock()

    incident = await create_incident_from_public_form(
        fake_session,
        fio="",
        full_address="",
        region="Самарская область",
        city="г. Самара",
        street="ул. Мира, 5",
        coords="53.1, 50.2",
        photo_time="",
        bins="",
        photo_files=[],
        mno_id=str(mid),  # mno_reg НЕ передан → None → подтянется из МНО
    )
    # Явные адресные поля НЕ перекрыты значениями МНО.
    assert incident.city == "г. Самара"
    assert incident.street == "ул. Мира, 5"
    assert incident.coords == "53.1, 50.2"
    # Пустой mno_reg заполнен из МНО.
    assert incident.mno_reg == "63-04-777"


@pytest.mark.asyncio
async def test_public_service_resizes_full_and_thumb(fake_session, tmp_path, monkeypatch):
    """Валидное фото → принято и пере-кодировано: на диске FULL `{i}.jpg` + THUMB
    `{i}_thumb.jpg` (оба JPEG); thumb ≤400px и меньше full. Расширение всегда .jpg."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    fake_session.add = MagicMock()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="Волонтёр",
        full_address="",
        region="Самарская область",
        city="г. Самара",
        street="ул. Ленина, 1",
        coords="53.2, 50.1",
        photo_time="",
        bins="",
        # имя .png + content_type image/png — намеренно «врут»; формат даёт Pillow.
        photo_files=[_FakeUpload(_jpeg_bytes(), filename="photo.png", content_type="image/png")],
    )
    assert incident.photos == 1
    assert len(incident.photo_urls) == 1
    assert incident.photo_urls[0].endswith("0.jpg")

    incident_dir = tmp_path / "incidents" / str(incident.id)
    full = incident_dir / "0.jpg"
    thumb = incident_dir / "0_thumb.jpg"
    assert full.is_file()
    assert thumb.is_file()
    with Image.open(full) as f_img, Image.open(thumb) as t_img:
        assert f_img.format == "JPEG"
        assert t_img.format == "JPEG"
        assert max(t_img.size) <= 400
        assert max(t_img.size) < max(f_img.size)


@pytest.mark.asyncio
async def test_public_service_overlong_fields_truncated(fake_session):
    """Сверхдлинные текстовые поля отсекаются до ширины колонок (нет DataError/500)."""
    fake_session.add = MagicMock()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="и" * 400,
        full_address="",
        region="о" * 400,
        city="г" * 400,
        street="у" * 900,
        coords="5" * 200,  # колонка coords = String(64)
        photo_time="",
        bins="",
        photo_files=[],
    )
    assert len(incident.coords) == 64
    assert len(incident.fio) == 255
    assert len(incident.region) == 255
    assert len(incident.city) == 255
    assert len(incident.street) == 500


@pytest.mark.asyncio
async def test_public_service_saves_valid_incident_type_and_comment(fake_session):
    """Валидный код типа (есть в БД) + comment (стрипнутый) сохраняются на инциденте."""
    fake_session.add = MagicMock()
    # Валидность типа теперь проверяется по БД (code_exists) — мокаем «код найден».
    with patch(
        "app.services.intake.code_exists", new=AsyncMock(return_value=True)
    ):
        incident = await create_incident_from_public_form(
            fake_session,
            fio="Волонтёр",
            full_address="",
            region="Самарская область",
            city="г. Самара",
            street="ул. Ленина, 1",
            coords="",
            photo_time="",
            bins="",
            incident_type="fire",
            comment="  Баки переполнены  ",
            photo_files=[],
        )
    assert incident.incident_type == "fire"
    assert incident.comment == "Баки переполнены"


@pytest.mark.asyncio
async def test_public_service_garbage_incident_type_is_none(fake_session):
    """Неизвестный код типа (нет в БД) не пишется (мусор → None); пустой comment → None."""
    fake_session.add = MagicMock()
    # code_exists возвращает False → код отбрасывается (incident_type=None).
    with patch(
        "app.services.intake.code_exists", new=AsyncMock(return_value=False)
    ):
        incident = await create_incident_from_public_form(
            fake_session,
            fio="Волонтёр",
            full_address="",
            region="Самарская область",
            city="г. Самара",
            street="",
            coords="",
            photo_time="",
            bins="",
            incident_type="not_a_type",
            comment="   ",
            photo_files=[],
        )
    assert incident.incident_type is None
    assert incident.comment is None


@pytest.mark.asyncio
async def test_public_service_incident_type_defaults_none(fake_session):
    """Без incident_type/comment (значения по умолчанию) → оба None."""
    fake_session.add = MagicMock()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="Волонтёр",
        full_address="",
        region="Самарская область",
        city="г. Самара",
        street="",
        coords="",
        photo_time="",
        bins="",
        photo_files=[],
    )
    assert incident.incident_type is None
    assert incident.comment is None


@pytest.mark.asyncio
async def test_public_service_saves_volunteer_id(fake_session):
    """volunteer_id (автор из приложения) проставляется на инциденте; по умолчанию None."""
    fake_session.add = MagicMock()
    vol_id = uuid4()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="Волонтёр",
        full_address="",
        region="Самарская область",
        city="г. Самара",
        street="ул. Ленина, 1",
        coords="",
        photo_time="",
        bins="",
        photo_files=[],
        volunteer_id=vol_id,
    )
    assert incident.volunteer_id == vol_id

    # Без volunteer_id (аноним/веб-форма) → NULL.
    anon = await create_incident_from_public_form(
        fake_session,
        fio="Аноним",
        full_address="",
        region="Самарская область",
        city="г. Самара",
        street="ул. Ленина, 1",
        coords="",
        photo_time="",
        bins="",
        photo_files=[],
    )
    assert anon.volunteer_id is None


@pytest.mark.asyncio
async def test_public_service_saves_mno_reg(fake_session):
    """mno_reg (рег-номер выбранного МНО) стрипается и сохраняется на инциденте."""
    fake_session.add = MagicMock()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="Волонтёр",
        full_address="",
        region="Самарская область",
        city="г. Самара",
        street="Бульварная улица, 18",
        coords="53.231410, 50.166820",
        photo_time="",
        bins="",
        mno_reg="  63-04-001162  ",
        photo_files=[],
    )
    assert incident.mno_reg == "63-04-001162"


@pytest.mark.asyncio
async def test_public_service_blank_mno_reg_is_none(fake_session):
    """Пустой mno_reg → NULL (МНО не выбрано, адрес введён вручную)."""
    fake_session.add = MagicMock()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="Волонтёр",
        full_address="",
        region="Самарская область",
        city="г. Самара",
        street="ул. Ленина, 1",
        coords="",
        photo_time="",
        bins="",
        mno_reg="   ",
        photo_files=[],
    )
    assert incident.mno_reg is None


@pytest.mark.asyncio
async def test_public_service_overlong_mno_reg_truncated(fake_session):
    """Сверхдлинный mno_reg отсекается до ширины колонки String(64) (нет DataError)."""
    fake_session.add = MagicMock()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="Волонтёр",
        full_address="",
        region="Самарская область",
        city="г. Самара",
        street="ул. Ленина, 1",
        coords="",
        photo_time="",
        bins="",
        mno_reg="7" * 200,
        photo_files=[],
    )
    assert len(incident.mno_reg) == 64


@pytest.mark.asyncio
async def test_public_service_saves_mno_id(fake_session):
    """Валидный mno_id (UUID выбранного МНО) сохраняется на инциденте как UUID-объект."""
    fake_session.add = MagicMock()
    mno_id = uuid4()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="Волонтёр",
        full_address="",
        region="Самарская область",
        city="г. Самара",
        street="Бульварная улица, 18",
        coords="53.231410, 50.166820",
        photo_time="",
        bins="",
        mno_reg="63-04-001162",
        mno_id=f"  {mno_id}  ",
        photo_files=[],
    )
    assert incident.mno_id == mno_id


@pytest.mark.asyncio
async def test_public_service_blank_mno_id_is_none(fake_session):
    """Пустой mno_id → NULL (МНО не выбрано, адрес введён вручную)."""
    fake_session.add = MagicMock()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="Волонтёр",
        full_address="",
        region="Самарская область",
        city="г. Самара",
        street="ул. Ленина, 1",
        coords="",
        photo_time="",
        bins="",
        mno_id="   ",
        photo_files=[],
    )
    assert incident.mno_id is None


@pytest.mark.asyncio
async def test_public_service_garbage_mno_id_is_none(fake_session):
    """Мусорный (не-UUID) mno_id → NULL, а не падение INSERT-а."""
    fake_session.add = MagicMock()
    incident = await create_incident_from_public_form(
        fake_session,
        fio="Волонтёр",
        full_address="",
        region="Самарская область",
        city="г. Самара",
        street="ул. Ленина, 1",
        coords="",
        photo_time="",
        bins="",
        mno_id="not-a-valid-uuid",
        photo_files=[],
    )
    assert incident.mno_id is None


# --------------------------------------------------------------------------- #
# GET /photo/{incident_id}/{filename} — анти-traversal / 404                   #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_photo_bad_uuid_404(client):
    """Невалидный UUID в incident_id → 404 NOT_FOUND."""
    resp = await client.get("/api/v1/intake/photo/not-a-uuid/0.jpg")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_photo_bad_filename_404(client):
    """Имя файла вне белого списка (не `\\d+\\.(jpg|jpeg|png|webp)`) → 404."""
    valid_uuid = str(uuid4())
    # Расширение не из белого списка → guard отбивает (traversal-классы тоже).
    resp = await client.get(f"/api/v1/intake/photo/{valid_uuid}/0.txt")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_photo_missing_file_404(client):
    """Валидные UUID и имя файла, но файла нет на диске → 404."""
    valid_uuid = str(uuid4())
    resp = await client.get(f"/api/v1/intake/photo/{valid_uuid}/0.jpg")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# --------------------------------------------------------------------------- #
# Приём из Макс-бота: POST /api/v1/intake/max                                  #
# --------------------------------------------------------------------------- #


def _max_session(fake_session):
    """Готовит fake_session: add копит объекты, flush присваивает UUID инциденту."""
    added: list = []
    fake_session.add = MagicMock(side_effect=added.append)

    async def _flush(*args, **kwargs):
        for obj in added:
            if isinstance(obj, Incident) and getattr(obj, "id", None) is None:
                obj.id = uuid4()

    fake_session.flush = AsyncMock(side_effect=_flush)
    return added


@pytest.mark.asyncio
async def test_max_intake_creates_incident(client, fake_session, monkeypatch, tmp_path):
    """POST /max (валидный токен + фото) → 200; source='max', msg выставлен,
    region/city/street/coords взяты из разбора DaData Clean (clean_address)."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    added = _max_session(fake_session)

    cleaned = {
        "region": "Самарская обл",
        "city": "г Кинель",
        "street": "ул Маяковского, д 41",
        "coords": "53.2, 50.6",
        "geo_lat": "53.2",
        "geo_lon": "50.6",
    }
    fake_clean = AsyncMock(return_value=cleaned)
    quote = AsyncMock(return_value="«цитата о природе» — Автор")
    # ai_parse_incident → None: проверяем именно путь DaData Clean (без shell-out CLI).
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=None)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=fake_clean), patch(
        "app.api.v1.intake.quotes_service.nature_quote", new=quote
    ):
        resp = await client.post(
            "/api/v1/intake/max",
            headers={"X-Intake-Token": "secret-token"},
            data={
                "text": "Самарская область, Кинель, Маяковского 41",
                "msg_id": "msg-123",
                "msg_url": "https://max.ru/c/-75787158905457/AZ8DNeZnbkM",
                "sender_name": "Иванов Иван",
                "photo_time": "2026-04-26T08:05:00",
            },
            files=[("photos", ("0.jpg", BytesIO(_FAKE_IMG), "image/jpeg"))],
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["quote"] == "«цитата о природе» — Автор"

    incident = next(o for o in added if isinstance(o, Incident))
    assert body["incident_id"] == str(incident.id)
    assert incident.source == "max"
    assert incident.status == "new"
    assert incident.fio == "Иванов Иван"
    assert incident.msg == "msg-123"
    # Готовый https-URL сообщения проброшен из формы и сохранён как есть.
    assert incident.msg_url == "https://max.ru/c/-75787158905457/AZ8DNeZnbkM"
    # ТИП региона нормализован к полной форме («обл» → «область»); город DaData
    # «г Кинель» оставлен как есть (унификация типа пункта неоднозначна).
    assert incident.region == "Самарская область"
    assert incident.city == "г Кинель"
    assert incident.street == "ул Маяковского, д 41"
    assert incident.coords == "53.2, 50.6"
    assert incident.photos == 1
    assert len(incident.photo_urls) == 1
    # Цитата сохранена на инциденте (2-й commit в роуте).
    assert incident.quote == "«цитата о природе» — Автор"
    fake_clean.assert_awaited_once()
    fake_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_max_intake_wrong_token_403(client, monkeypatch):
    """Неверный X-Intake-Token → 403 FORBIDDEN, сервис не вызывается."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    create = AsyncMock()
    with patch(
        "app.api.v1.intake.intake_service.create_incident_from_max",
        new=create,
    ):
        resp = await client.post(
            "/api/v1/intake/max",
            headers={"X-Intake-Token": "WRONG"},
            data={"text": "адрес", "msg_id": "m-1", "sender_name": "Кто-то"},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_max_intake_disabled_when_unset(client, monkeypatch):
    """Токен приёма не сконфигурирован → 503 INTAKE_DISABLED."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", None)
    resp = await client.post(
        "/api/v1/intake/max",
        headers={"X-Intake-Token": "anything"},
        data={"text": "адрес", "msg_id": "m-1", "sender_name": "Кто-то"},
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "INTAKE_DISABLED"


@pytest.mark.asyncio
async def test_max_intake_falls_back_to_heuristic(client, fake_session, monkeypatch):
    """clean_address → None: разбор адреса уходит в эвристику (без 500), coords=''."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    added = _max_session(fake_session)

    fake_clean = AsyncMock(return_value=None)
    quote = AsyncMock(return_value="«цитата» — Автор")
    # ai_parse_incident → None: разбор уходит в DaData Clean → эвристику.
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=None)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=fake_clean), patch(
        "app.api.v1.intake.quotes_service.nature_quote", new=quote
    ):
        resp = await client.post(
            "/api/v1/intake/max",
            headers={"X-Intake-Token": "secret-token"},
            data={
                "text": "Самарская область, г. Кинель, ул. Маяковского, 41",
                "msg_id": "m-9",
                "sender_name": "Петров",
            },
        )

    assert resp.status_code == 200
    incident = next(o for o in added if isinstance(o, Incident))
    assert incident.source == "max"
    assert incident.msg == "m-9"
    assert incident.region == "Самарская область"
    assert incident.city == "г. Кинель"
    assert incident.street == "ул. Маяковского, 41"
    assert incident.coords == ""
    fake_clean.assert_awaited_once()


# --------------------------------------------------------------------------- #
# AI-разбор адреса Макс-обращения: ai_parse_incident → create_incident_from_max #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_max_service_ai_address_dadata_wins_coords(fake_session):
    """AI извлёк адрес → DaData стандартизирует; coords/поля DaData авторитетны.

    clean_address вызывается композицией region+city+street из AI; результат
    DaData (стандартизированные поля + геокод) перекрывает «сырой» AI.
    """
    _max_session(fake_session)
    ai = {
        "region": "Нижегородская область",
        "city": "Нижний Новгород",
        "street": "улица Сергея Есенина, 38",
        "coords": "",  # координат в тексте нет → AI оставил пусто
        "time": "",
    }
    cleaned = {
        "region": "Нижегородская обл",
        "city": "г Нижний Новгород",
        "street": "ул Сергея Есенина, д 38",
        "coords": "56.23, 44.05",
        "geo_lat": "56.23",
        "geo_lon": "44.05",
    }
    fake_ai = AsyncMock(return_value=ai)
    fake_clean = AsyncMock(return_value=cleaned)
    with patch("app.services.intake.ai_parse_incident", new=fake_ai), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=fake_clean):
        incident = await create_incident_from_max(
            fake_session,
            text="Нижегородская область, г. Нижний Новгород, улица Сергея Есенина, 38",
            msg_id="m-1",
            sender_name="Иван",
            photo_files=[],
        )

    assert incident.source == "max"
    # DaData отдала «Нижегородская обл» → нормализовано к полной форме «область».
    assert incident.region == "Нижегородская область"
    assert incident.city == "г Нижний Новгород"  # DaData (тип пункта не трогаем)
    assert incident.street == "ул Сергея Есенина, д 38"  # DaData
    assert incident.coords == "56.23, 44.05"  # DaData геокод авторитетен
    fake_ai.assert_awaited_once()
    fake_clean.assert_awaited_once()
    addr_arg = fake_clean.call_args.args[0]
    assert "Нижегородская область" in addr_arg
    assert "улица Сергея Есенина, 38" in addr_arg


@pytest.mark.asyncio
async def test_max_service_ai_address_no_dadata_uses_ai(fake_session):
    """AI дал адрес, DaData недоступна (None) → поля AI + координаты из AI."""
    _max_session(fake_session)
    ai = {
        "region": "Нижегородская область",
        "city": "Нижний Новгород",
        "street": "улица Сергея Есенина, 38 (Радар №116495)",
        "coords": "56.23, 44.05",
        "time": "",
    }
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=ai)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        incident = await create_incident_from_max(
            fake_session,
            text="свободный текст обращения",
            msg_id="m-2",
            sender_name="Пётр",
            photo_files=[],
        )

    assert incident.region == "Нижегородская область"
    assert incident.city == "Нижний Новгород"
    assert incident.street == "улица Сергея Есенина, 38 (Радар №116495)"
    assert incident.coords == "56.23, 44.05"  # ai.coords как фолбэк координат


@pytest.mark.asyncio
async def test_max_service_ai_none_falls_back_heuristic(fake_session):
    """ai_parse_incident → None: путь DaData Clean → эвристика (без 500), coords=''."""
    _max_session(fake_session)
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=None)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        incident = await create_incident_from_max(
            fake_session,
            text="Самарская область, г. Кинель, ул. Маяковского, 41",
            msg_id="m-3",
            sender_name="Сидоров",
            photo_files=[],
        )

    assert incident.region == "Самарская область"
    assert incident.city == "г. Кинель"
    assert incident.street == "ул. Маяковского, 41"
    assert incident.coords == ""


@pytest.mark.asyncio
async def test_max_service_ai_time_sets_photo_time(fake_session):
    """ai.time в формате ЧЧ:ММ → photo_time = сегодня@ЧЧ:ММ (override)."""
    _max_session(fake_session)
    ai = {"region": "", "city": "", "street": "", "coords": "", "time": "10:28"}
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=ai)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        incident = await create_incident_from_max(
            fake_session,
            text="ул. Есенина, 38, 10:28",
            msg_id="m-4",
            sender_name="Аноним",
            photo_time=None,
            photo_files=[],
        )

    assert incident.photo_time is not None
    assert incident.photo_time.tzinfo is not None
    assert (incident.photo_time.hour, incident.photo_time.minute) == (10, 28)


@pytest.mark.asyncio
async def test_max_service_saves_comment_from_ai(fake_session):
    """AI вернул comment (прочая не-адресная инфа) → сохраняется на инциденте."""
    _max_session(fake_session)
    ai = {
        "region": "Краснодарский край",
        "city": "Сочи",
        "street": "Олимпийская улица, 38/9",
        "coords": "",
        "time": "",
        "comment": "Бахтин Владимир Вадимович; Радар №116434; Баки раздельного сбора отсутствуют",
    }
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=ai)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        incident = await create_incident_from_max(
            fake_session,
            text="Бахтин ... Краснодарский край Г.Сочи Олимпийская улица 38/9 (Радар №116434) ...",
            msg_id="m-comment",
            sender_name="Бахтин",
            photo_files=[],
        )

    assert incident.comment == (
        "Бахтин Владимир Вадимович; Радар №116434; Баки раздельного сбора отсутствуют"
    )
    # Прочая инфа осталась ВНЕ адреса.
    assert incident.street == "Олимпийская улица, 38/9"


@pytest.mark.asyncio
async def test_max_service_empty_comment_is_none(fake_session):
    """AI дал пустой/отсутствующий comment → incident.comment = None (не '')."""
    _max_session(fake_session)
    ai = {"region": "", "city": "", "street": "", "coords": "", "time": "", "comment": ""}
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=ai)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        incident = await create_incident_from_max(
            fake_session,
            text="Самарская область, г. Кинель, ул. Маяковского, 41",
            msg_id="m-nc",
            sender_name="Иван",
            photo_files=[],
        )

    assert incident.comment is None


@pytest.mark.asyncio
async def test_max_service_saves_msg_url(fake_session):
    """Непустой msg_url сохраняется на инциденте КАК ЕСТЬ (полный https-URL)."""
    _max_session(fake_session)
    url = "https://max.ru/c/-75787158905457/AZ8DNeZnbkM"
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=None)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        incident = await create_incident_from_max(
            fake_session,
            text="Самарская область, г. Кинель, ул. Маяковского, 41",
            msg_id="m-url",
            msg_url=url,
            sender_name="Иван",
            photo_files=[],
        )

    assert incident.msg == "m-url"
    assert incident.msg_url == url


@pytest.mark.asyncio
async def test_max_service_blank_msg_url_is_none(fake_session):
    """Пустой/пробельный msg_url (личка с ботом) → msg_url = None (ссылка не строится)."""
    _max_session(fake_session)
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=None)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        incident = await create_incident_from_max(
            fake_session,
            text="Самарская область, г. Кинель, ул. Маяковского, 41",
            msg_id="m-blank",
            msg_url="   ",
            sender_name="Иван",
            photo_files=[],
        )

    assert incident.msg == "m-blank"
    assert incident.msg_url is None


# --------------------------------------------------------------------------- #
# ai_parse_incident — извлечение JSON из ответа CLI (DB-free, CLI замокан)     #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_ai_parse_incident_extracts_fenced_json():
    """Ответ CLI в ```json …``` → распарсенный dict с 5 строковыми ключами."""
    from app.services import incident_parse

    raw = (
        "```json\n"
        '{"region": "Нижегородская область", "city": "Нижний Новгород", '
        '"street": "ул. Есенина, 38", "coords": "", "time": "10:28", '
        '"comment": "Радар №116495; Баки раздельного сбора отсутствуют"}\n'
        "```"
    )
    with patch(
        "app.services.incident_parse.claude_cli_complete",
        new=AsyncMock(return_value=raw),
    ):
        result = await incident_parse.ai_parse_incident("какой-то свободный текст")

    assert result == {
        "region": "Нижегородская область",
        "city": "Нижний Новгород",
        "street": "ул. Есенина, 38",
        "coords": "",
        "time": "10:28",
        "comment": "Радар №116495; Баки раздельного сбора отсутствуют",
    }


@pytest.mark.asyncio
async def test_ai_parse_incident_prose_and_missing_keys():
    """JSON в прозе + отсутствующие ключи → извлекаем, отсутствующие → ''."""
    from app.services import incident_parse

    raw = 'Вот результат: {"region": "Самарская область", "city": "Кинель"} — готово.'
    with patch(
        "app.services.incident_parse.claude_cli_complete",
        new=AsyncMock(return_value=raw),
    ):
        result = await incident_parse.ai_parse_incident("текст")

    assert result == {
        "region": "Самарская область",
        "city": "Кинель",
        "street": "",
        "coords": "",
        "time": "",
        "comment": "",
    }


@pytest.mark.asyncio
async def test_ai_parse_incident_garbage_returns_none():
    """Ответ без JSON-объекта → None (фолбэк на DaData/эвристику)."""
    from app.services import incident_parse

    with patch(
        "app.services.incident_parse.claude_cli_complete",
        new=AsyncMock(return_value="это не json, извините"),
    ):
        assert await incident_parse.ai_parse_incident("текст") is None


@pytest.mark.asyncio
async def test_ai_parse_incident_cli_unavailable_returns_none():
    """CLI недоступен (claude_cli_complete → None) → None."""
    from app.services import incident_parse

    with patch(
        "app.services.incident_parse.claude_cli_complete",
        new=AsyncMock(return_value=None),
    ):
        assert await incident_parse.ai_parse_incident("текст") is None


@pytest.mark.asyncio
async def test_ai_parse_incident_uses_parse_model(monkeypatch):
    """ai_parse_incident дёргает CLI с settings.CLAUDE_PARSE_MODEL (не QUOTE)."""
    from app.services import incident_parse

    monkeypatch.setattr(settings, "CLAUDE_PARSE_MODEL", "sonnet")
    monkeypatch.setattr(settings, "CLAUDE_QUOTE_MODEL", "haiku")

    fake_cli = AsyncMock(
        return_value='{"region": "Москва", "city": "Москва", "street": "", '
        '"coords": "", "time": ""}'
    )
    with patch("app.services.incident_parse.claude_cli_complete", new=fake_cli):
        result = await incident_parse.ai_parse_incident("Москва, какой-то адрес")

    assert result is not None
    fake_cli.assert_awaited_once()
    # Модель разбора — CLAUDE_PARSE_MODEL (sonnet), НЕ цитатная haiku.
    assert fake_cli.await_args.kwargs["model"] == "sonnet"
    assert fake_cli.await_args.kwargs["model"] != settings.CLAUDE_QUOTE_MODEL


# --------------------------------------------------------------------------- #
# resolve_address — единый конвейер разбора адреса (мок ai + clean_address)    #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_resolve_address_dirty_text_ai_dadata():
    """Грязный текст (ФИО+дата+описание) → AI чистит, DaData стандартизирует.

    AI извлёк регион/город/улицу из мусора; resolve_address склеивает их и
    отдаёт в clean_address; результат DaData (поля + геокод) авторитетен.
    """
    from app.services import intake

    dirty = (
        "Бахтин Владимир Вадимович Краснодарский край Г.Сочи "
        "27.06.2026 19:06 Олимпийская улица 38/9 Баки раздельного сбора отсутствуют"
    )
    ai = {
        "region": "Краснодарский край",
        "city": "Сочи",
        "street": "Олимпийская улица, 38/9",
        "coords": "",
        "time": "19:06",
    }
    cleaned = {
        "region": "Краснодарский край",
        "city": "г Сочи",
        "street": "ул Олимпийская, д 38/9",
        "coords": "43.40, 39.95",
        "geo_lat": "43.40",
        "geo_lon": "39.95",
    }
    fake_ai = AsyncMock(return_value=ai)
    fake_clean = AsyncMock(return_value=cleaned)
    with patch("app.services.intake.ai_parse_incident", new=fake_ai), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=fake_clean):
        region, city, street, coords = await intake.resolve_address(dirty)

    # ФИО/дата/описание из текста НЕ просочились — регион/город разделены.
    assert region == "Краснодарский край"
    assert city == "г Сочи"
    assert street == "ул Олимпийская, д 38/9"
    assert coords == "43.40, 39.95"
    fake_ai.assert_awaited_once()  # ai не передан → парсится внутри
    fake_clean.assert_awaited_once()
    addr_arg = fake_clean.call_args.args[0]
    assert "Краснодарский край" in addr_arg
    assert "Сочи" in addr_arg
    assert "Бахтин" not in addr_arg  # ФИО заявителя не попало в адрес


@pytest.mark.asyncio
async def test_resolve_address_ai_only_when_dadata_down():
    """AI дал адрес, DaData недоступна (None) → поля AI + координаты AI."""
    from app.services import intake

    ai = {
        "region": "Краснодарский край",
        "city": "Сочи",
        "street": "Олимпийская улица, 38/9",
        "coords": "43.40, 39.95",
        "time": "",
    }
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=ai)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        region, city, street, coords = await intake.resolve_address("грязный текст")

    assert region == "Краснодарский край"
    assert city == "Сочи"
    assert street == "Олимпийская улица, 38/9"
    assert coords == "43.40, 39.95"  # координаты AI как фолбэк


@pytest.mark.asyncio
async def test_resolve_address_ai_none_dadata_raw():
    """AI → None, но clean_address(raw) разбирает текст → поля DaData."""
    from app.services import intake

    cleaned = {
        "region": "Самарская обл",
        "city": "г Кинель",
        "street": "ул Маяковского, д 41",
        "coords": "53.2, 50.6",
        "geo_lat": "53.2",
        "geo_lon": "50.6",
    }
    fake_ai = AsyncMock(return_value=None)
    fake_clean = AsyncMock(return_value=cleaned)
    with patch("app.services.intake.ai_parse_incident", new=fake_ai), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=fake_clean):
        region, city, street, coords = await intake.resolve_address(
            "Самарская область, г. Кинель, ул. Маяковского, 41"
        )

    assert region == "Самарская область"  # «обл» нормализовано к полной форме
    assert city == "г Кинель"
    assert street == "ул Маяковского, д 41"
    assert coords == "53.2, 50.6"


@pytest.mark.asyncio
async def test_resolve_address_all_none_heuristic():
    """AI → None и DaData → None → эвристика _parse_address (coords='')."""
    from app.services import intake

    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=None)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        region, city, street, coords = await intake.resolve_address(
            "Самарская область, г. Кинель, ул. Маяковского, 41"
        )

    assert region == "Самарская область"
    assert city == "г. Кинель"
    assert street == "ул. Маяковского, 41"
    assert coords == ""


@pytest.mark.asyncio
async def test_resolve_address_reuses_provided_ai():
    """ai передан явно → resolve_address НЕ дёргает CLI повторно (один вызов)."""
    from app.services import intake

    ai = {
        "region": "Краснодарский край",
        "city": "Сочи",
        "street": "Олимпийская улица, 38/9",
        "coords": "",
        "time": "",
    }
    fake_ai = AsyncMock(return_value=ai)
    with patch("app.services.intake.ai_parse_incident", new=fake_ai), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        region, city, street, coords = await intake.resolve_address(
            "грязный текст", ai=ai
        )

    assert (region, city, street) == ("Краснодарский край", "Сочи", "Олимпийская улица, 38/9")
    fake_ai.assert_not_awaited()  # ai отдан готовым → CLI не вызывался


@pytest.mark.asyncio
async def test_resolve_address_uses_geocode_coords():
    """AI дал адрес → бесплатный geocode_address даёт координаты/поля; Clean НЕ нужен.

    geocode (Подсказки) возвращает результат → платный clean_address как фолбэк
    НЕ вызывается. street из geocode уже с домом — проброшен как есть.
    """
    from app.services import intake

    ai = {
        "region": "Самарская область",
        "city": "Кинель",
        "street": "Маяковского, 41",
        "coords": "",
        "time": "",
    }
    geocoded = {
        "region": "Самарская обл",
        "city": "г Кинель",
        "street": "ул Маяковского, 41",
        "coords": "53.22, 50.63",
        "geo_lat": "53.22",
        "geo_lon": "50.63",
    }
    fake_geocode = AsyncMock(return_value=geocoded)
    fake_clean = AsyncMock(return_value=None)
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=ai)
    ), patch("app.services.intake.geocode_address", new=fake_geocode), patch(
        "app.services.intake.clean_address", new=fake_clean
    ):
        region, city, street, coords = await intake.resolve_address(
            "Самарская область, Кинель, Маяковского 41"
        )

    # geocode (Подсказки) дал «Самарская обл» → нормализовано к полной форме.
    assert region == "Самарская область"
    assert city == "г Кинель"
    assert street == "ул Маяковского, 41"  # дом сохранён
    assert coords == "53.22, 50.63"  # геокод из бесплатных Подсказок
    fake_geocode.assert_awaited_once()
    fake_clean.assert_not_awaited()  # geocode дал результат → платный Clean не нужен


@pytest.mark.asyncio
async def test_ai_parse_incident_empty_text_skips_cli():
    """Пустой текст → None, CLI вообще не вызывается."""
    from app.services import incident_parse

    cli = AsyncMock(return_value='{"region": "x"}')
    with patch("app.services.incident_parse.claude_cli_complete", new=cli):
        assert await incident_parse.ai_parse_incident("   ") is None
    cli.assert_not_awaited()


# Цитата теперь берётся СЛУЧАЙНО из таблицы quotes (claude CLI убран) — тесты пула
# и выборки/фолбэка живут в tests/test_quotes.py.


# --------------------------------------------------------------------------- #
# Групповые уведомления Макс: GET /pending-notify, POST /mark-notified         #
# --------------------------------------------------------------------------- #


def _pending_incident() -> Incident:
    """Инцидент-кандидат на уведомление (notified_at IS NULL) с полями для схемы."""
    inc = Incident(
        source="max",
        status="new",
        fio="Иванов Иван",
        region="Самарская обл",
        city="г Кинель",
        street="ул Маяковского, д 41",
        coords="53.2, 50.6",
        comment="Радар №116434; Баки раздельного сбора отсутствуют",
        photo_time=None,
        photos=1,
        photo_urls=["/api/v1/intake/photo/x/0.jpg"],
        msg="msg-1",
        msg_url="https://max.ru/c/-75787158905457/AZ8DNeZnbkM",
        quote="«цитата» — Автор",
    )
    inc.id = uuid4()
    inc.notified_at = None
    return inc


@pytest.mark.asyncio
async def test_pending_notify_returns_unnotified(client, monkeypatch):
    """GET /pending-notify с токеном → список не уведомлённых инцидентов."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    inc = _pending_incident()
    lister = AsyncMock(return_value=[inc])
    with patch(
        "app.api.v1.intake.incident_service.list_pending_notify",
        new=lister,
    ):
        resp = await client.get(
            "/api/v1/intake/pending-notify",
            headers={"X-Intake-Token": "secret-token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["incidents"]) == 1
    item = body["incidents"][0]
    assert item["id"] == str(inc.id)
    assert item["source"] == "max"
    assert item["fio"] == "Иванов Иван"
    assert item["city"] == "г Кинель"
    assert item["photo_urls"] == ["/api/v1/intake/photo/x/0.jpg"]
    assert item["msg"] == "msg-1"
    # Готовый https-URL сообщения отдаётся боту для ссылки в группе (как есть).
    assert item["msg_url"] == "https://max.ru/c/-75787158905457/AZ8DNeZnbkM"
    # comment отдаётся боту для строки «Комментарий: …» в уведомлении группы.
    assert item["comment"] == "Радар №116434; Баки раздельного сбора отсутствуют"
    assert item["quote"] == "«цитата» — Автор"
    assert item["photo_time"] is None
    lister.assert_awaited_once()


@pytest.mark.asyncio
async def test_pending_notify_requires_token_403(client, monkeypatch):
    """GET /pending-notify без X-Intake-Token → 403, сервис не вызывается."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    lister = AsyncMock(return_value=[])
    with patch(
        "app.api.v1.intake.incident_service.list_pending_notify",
        new=lister,
    ):
        resp = await client.get("/api/v1/intake/pending-notify")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    lister.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_notify_disabled_when_unset(client, monkeypatch):
    """Токен приёма не сконфигурирован → 503 INTAKE_DISABLED."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", None)
    resp = await client.get(
        "/api/v1/intake/pending-notify",
        headers={"X-Intake-Token": "anything"},
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "INTAKE_DISABLED"


@pytest.mark.asyncio
async def test_mark_notified_marks_and_commits(client, monkeypatch):
    """POST /mark-notified с токеном → {"marked": N}; сервис вызван с id, commit."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    ids = [uuid4(), uuid4()]
    marker = AsyncMock(return_value=2)
    with patch(
        "app.api.v1.intake.incident_service.mark_notified",
        new=marker,
    ):
        resp = await client.post(
            "/api/v1/intake/mark-notified",
            headers={"X-Intake-Token": "secret-token"},
            json={"ids": [str(i) for i in ids]},
        )
    assert resp.status_code == 200
    assert resp.json() == {"marked": 2}
    marker.assert_awaited_once()
    passed_ids = marker.call_args.args[1]
    assert passed_ids == ids


@pytest.mark.asyncio
async def test_mark_notified_requires_token_403(client, monkeypatch):
    """POST /mark-notified без X-Intake-Token → 403, сервис не вызывается."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    marker = AsyncMock(return_value=0)
    with patch(
        "app.api.v1.intake.incident_service.mark_notified",
        new=marker,
    ):
        resp = await client.post(
            "/api/v1/intake/mark-notified",
            json={"ids": [str(uuid4())]},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    marker.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_notified_service_sets_notified_at():
    """Прямой вызов mark_notified: формирует UPDATE notified_at, возвращает rowcount."""
    from app.services import incident as incident_service

    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(rowcount=2))
    ids = [uuid4(), uuid4()]

    marked = await incident_service.mark_notified(session, ids)

    assert marked == 2
    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_notified_service_empty_noop():
    """Пустой список id → 0 без обращения к БД."""
    from app.services import incident as incident_service

    session = AsyncMock()
    assert await incident_service.mark_notified(session, []) == 0
    session.execute.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Выбор МНО в Макс-боте: nearest_mno (haversine + bbox-предфильтр)             #
# --------------------------------------------------------------------------- #


def _nearest_session(mnos):
    """Fake session: execute → результат, чей scalars().all() отдаёт заданный список МНО."""
    session = AsyncMock()
    res = MagicMock()
    res.scalars.return_value.all.return_value = mnos
    session.execute = AsyncMock(return_value=res)
    return session


def _mno_point(lat, lon, name="П", **kw):
    """Mno с координатами (или lat/lon=None) и произвольными адресными полями."""
    m = Mno(
        name=name,
        address=kw.get("address", "адрес"),
        city=kw.get("city", "город"),
        coords=kw.get("coords", (f"{lat}, {lon}" if lat is not None else "")),
        region_code=kw.get("region_code", "63"),
        reg=kw.get("reg", ""),
        lat=lat,
        lon=lon,
    )
    m.id = uuid4()
    return m


@pytest.mark.asyncio
async def test_nearest_mno_orders_filters_and_returns_fields():
    """nearest_mno: сортировка по расстоянию, отсев далёких (>30 км) и без координат."""
    center_lat, center_lon = 55.75, 37.62
    near = _mno_point(55.751, 37.621, name="near", reg="78-06-002210")
    mid = _mno_point(55.76, 37.63, name="mid")
    far_in = _mno_point(55.80, 37.70, name="far_in")  # ~7 км — в радиусе
    far_out = _mno_point(56.20, 38.50, name="far_out")  # >30 км — отброшен
    nocoords = _mno_point(None, None, name="nocoords")  # без координат — отброшен
    # порядок на входе намеренно перемешан
    session = _nearest_session([mid, far_out, near, nocoords, far_in])

    res = await mno_service.nearest_mno(
        session, center_lat, center_lon, limit=5, max_km=30.0
    )

    ids = [r["id"] for r in res]
    assert ids == [str(near.id), str(mid.id), str(far_in.id)]
    assert str(far_out.id) not in ids
    assert str(nocoords.id) not in ids
    # расстояние — целые метры по возрастанию
    dists = [r["distance_m"] for r in res]
    assert dists == sorted(dists)
    assert all(isinstance(d, int) for d in dists)
    # поля площадки проброшены; id — строка
    first = res[0]
    assert first["name"] == "near"
    # реестровый № площадки проброшен (бот показывает его в списке кандидатов)
    assert first["reg"] == "78-06-002210"
    assert first["lat"] == 55.751 and first["lon"] == 37.621
    assert isinstance(first["id"], str)
    assert {"address", "city", "coords"} <= set(first.keys())


@pytest.mark.asyncio
async def test_nearest_mno_respects_limit():
    """limit срезает выдачу после сортировки по расстоянию."""
    near = _mno_point(55.751, 37.621, name="near")
    mid = _mno_point(55.76, 37.63, name="mid")
    far_in = _mno_point(55.80, 37.70, name="far_in")
    session = _nearest_session([far_in, near, mid])

    res = await mno_service.nearest_mno(session, 55.75, 37.62, limit=2, max_km=30.0)
    assert [r["name"] for r in res] == ["near", "mid"]


@pytest.mark.asyncio
async def test_nearest_mno_radius_excludes_all():
    """Все МНО дальше max_km → пустой список."""
    a = _mno_point(60.0, 40.0, name="a")
    b = _mno_point(50.0, 30.0, name="b")
    session = _nearest_session([a, b])
    res = await mno_service.nearest_mno(session, 55.75, 37.62, max_km=5.0)
    assert res == []


# --------------------------------------------------------------------------- #
# POST /intake/max/prepare — разбор адреса + ближайшие МНО (ничего не пишет)   #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_prepare_max_need_address_when_no_coords(fake_session):
    """Координаты не распознаны → status need_address; parsed с region/city; МНО не ищем."""
    with patch(
        "app.services.intake.ai_parse_incident",
        new=AsyncMock(return_value={"comment": "Радар №1", "time": ""}),
    ), patch(
        "app.services.intake.resolve_address",
        new=AsyncMock(return_value=("Самарская область", "г. Самара", "", "")),
    ), patch("app.services.mno.nearest_mno", new=AsyncMock()) as near:
        res = await prepare_max_report(fake_session, text="текст без адреса")

    assert res["status"] == "need_address"
    assert res["parsed"]["region"] == "Самарская область"
    assert res["parsed"]["city"] == "г. Самара"
    assert res["parsed"]["coords"] == ""
    assert res["parsed"]["comment"] == "Радар №1"
    assert "candidates" not in res and "point" not in res
    near.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_max_ok_with_candidates(fake_session):
    """Координаты есть → status ok, point + кандидаты; ai.time ЧЧ:ММ → photo_time сегодня@ЧЧ:ММ."""
    candidates = [
        {
            "id": str(uuid4()),
            "name": "МНО-1",
            "address": "ул. 1",
            "city": "г. Самара",
            "coords": "53.21, 50.17",
            "lat": 53.21,
            "lon": 50.17,
            "distance_m": 120,
        }
    ]
    near = AsyncMock(return_value=candidates)
    with patch(
        "app.services.intake.ai_parse_incident",
        new=AsyncMock(return_value={"comment": "c", "time": "19:30"}),
    ), patch(
        "app.services.intake.resolve_address",
        new=AsyncMock(
            return_value=("Самарская область", "г. Самара", "ул. Ленина, 1", "53.2, 50.15")
        ),
    ), patch("app.services.mno.nearest_mno", new=near):
        res = await prepare_max_report(fake_session, text="Самара Ленина 1")

    assert res["status"] == "ok"
    assert res["point"] == {"lat": 53.2, "lon": 50.15}
    assert res["candidates"] == candidates
    assert res["parsed"]["street"] == "ул. Ленина, 1"
    assert res["parsed"]["coords"] == "53.2, 50.15"
    # ai.time «19:30» → сегодня@19:30 в ISO без секунд
    assert res["parsed"]["photo_time"].endswith("T19:30")
    near.assert_awaited_once()
    # nearest_mno вызван с распарсенными координатами точки обращения
    assert near.await_args.args[1] == 53.2
    assert near.await_args.args[2] == 50.15


@pytest.mark.asyncio
async def test_prepare_max_passthrough_photo_time_when_no_ai_time(fake_session):
    """Нет ai.time → parsed.photo_time = переданный вход как есть."""
    with patch(
        "app.services.intake.ai_parse_incident",
        new=AsyncMock(return_value={"comment": "", "time": ""}),
    ), patch(
        "app.services.intake.resolve_address",
        new=AsyncMock(return_value=("Р", "Г", "ул", "53.2, 50.15")),
    ), patch("app.services.mno.nearest_mno", new=AsyncMock(return_value=[])):
        res = await prepare_max_report(
            fake_session, text="Самара", photo_time="2026-04-26T08:05"
        )
    assert res["status"] == "ok"
    assert res["parsed"]["photo_time"] == "2026-04-26T08:05"
    assert res["candidates"] == []


# --------------------------------------------------------------------------- #
# POST /intake/max/finalize — create_incident_from_max_selected               #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_max_selected_creates_incident_without_mno(fake_session):
    """mno_id пуст → без привязки; source='max', поля/координаты/msg_url проброшены."""
    fake_session.add = MagicMock()
    incident = await create_incident_from_max_selected(
        fake_session,
        region="Самарская область",
        city="г. Самара",
        street="ул. Ленина, 1",
        coords="53.2, 50.15",
        comment="Радар №5",
        mno_id="",
        msg_id="m-1",
        sender_name="Иванов Иван",
        msg_url="https://max.ru/c/1/2",
        photo_time="2026-04-26T08:05:00",
        photo_files=[],
    )
    assert incident.source == "max"
    assert incident.status == "new"
    assert incident.fio == "Иванов Иван"
    assert incident.region == "Самарская область"
    assert incident.city == "г. Самара"
    assert incident.street == "ул. Ленина, 1"
    assert incident.coords == "53.2, 50.15"
    assert incident.comment == "Радар №5"
    assert incident.mno_id is None
    assert incident.mno_reg is None
    assert incident.msg == "m-1"
    assert incident.msg_url == "https://max.ru/c/1/2"
    assert incident.lat == 53.2 and incident.lon == 50.15
    assert incident.photo_time is not None and incident.photo_time.tzinfo is not None
    assert incident.photos == 0


@pytest.mark.asyncio
async def test_max_selected_backfills_address_from_mno(fake_session):
    """Выбран mno_id, адрес пуст → регион/город/адрес/координаты/mno_reg берутся из МНО."""
    mid = uuid4()
    mno = Mno(
        reg="63-04-001162",
        name="Контейнерная площадка",
        region_code="63",
        city="г. Самара",
        address="ул. Ленина, 1",
        coords="53.2, 50.6",
    )
    mno.id = mid
    # 1-й execute → сам МНО; 2-й → имя региона по region_code.
    res_mno = MagicMock()
    res_mno.scalar_one_or_none.return_value = mno
    res_region = MagicMock()
    res_region.scalar_one_or_none.return_value = "Самарская область"
    fake_session.execute = AsyncMock(side_effect=[res_mno, res_region])
    fake_session.add = MagicMock()

    incident = await create_incident_from_max_selected(
        fake_session,
        region="",
        city="",
        street="",
        coords="",
        comment="",
        mno_id=str(mid),
        msg_id="m-2",
        sender_name="Пётр",
        msg_url="",
        photo_time="",
        photo_files=[],
    )
    assert incident.source == "max"
    assert incident.mno_id == mid
    assert incident.region == "Самарская область"
    assert incident.city == "г. Самара"
    assert incident.street == "ул. Ленина, 1"
    assert incident.coords == "53.2, 50.6"
    assert incident.mno_reg == "63-04-001162"
    assert incident.lat == 53.2 and incident.lon == 50.6
    # пустой comment/msg_url → NULL
    assert incident.comment is None
    assert incident.msg_url is None


@pytest.mark.asyncio
async def test_max_selected_garbage_mno_id_is_none(fake_session):
    """Мусорный (не-UUID) mno_id → NULL (не роняет INSERT), бэкфилл не запускается."""
    fake_session.add = MagicMock()
    incident = await create_incident_from_max_selected(
        fake_session,
        region="Самарская область",
        city="г. Самара",
        street="ул. Ленина, 1",
        coords="53.2, 50.15",
        comment="",
        mno_id="not-a-uuid",
        msg_id="m-3",
        sender_name="Аноним",
        msg_url="",
        photo_time="",
        photo_files=[],
    )
    assert incident.mno_id is None
    fake_session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_max_selected_sets_incident_type(fake_session):
    """Валидный код типа (code_exists=True) сохраняется; мусор (False) → None."""
    fake_session.add = MagicMock()
    with patch("app.services.intake.code_exists", new=AsyncMock(return_value=True)):
        inc = await create_incident_from_max_selected(
            fake_session,
            region="",
            city="",
            street="",
            coords="",
            comment="",
            mno_id="",
            msg_id="m",
            sender_name="И",
            msg_url="",
            photo_time=None,
            photo_files=[],
            incident_type="fire",
        )
    assert inc.incident_type == "fire"
    with patch("app.services.intake.code_exists", new=AsyncMock(return_value=False)):
        inc2 = await create_incident_from_max_selected(
            fake_session,
            region="",
            city="",
            street="",
            coords="",
            comment="",
            mno_id="",
            msg_id="m",
            sender_name="И",
            msg_url="",
            photo_time=None,
            photo_files=[],
            incident_type="not_a_type",
        )
    assert inc2.incident_type is None


@pytest.mark.asyncio
async def test_max_finalize_route_creates_and_quotes(client, monkeypatch):
    """POST /max/finalize (токен + фото) → 200 ok+incident_id+quote; поля проброшены в сервис."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    fake_incident = Incident(source="max", status="new")
    fake_incident.id = uuid4()
    create = AsyncMock(return_value=fake_incident)
    quote = AsyncMock(return_value="«цитата» — Автор")
    mno_id = str(uuid4())
    with patch(
        "app.api.v1.intake.intake_service.create_incident_from_max_selected",
        new=create,
    ), patch("app.api.v1.intake.quotes_service.nature_quote", new=quote):
        resp = await client.post(
            "/api/v1/intake/max/finalize",
            headers={"X-Intake-Token": "secret-token"},
            data={
                "region": "Самарская область",
                "city": "г. Самара",
                "street": "ул. Ленина, 1",
                "coords": "53.2, 50.15",
                "comment": "Радар №5",
                "photo_time": "2026-04-26T08:05:00",
                "msg_id": "m-1",
                "sender_name": "Иванов Иван",
                "msg_url": "https://max.ru/c/1/2",
                "mno_id": mno_id,
            },
            files=[("photos", ("0.jpg", BytesIO(_FAKE_IMG), "image/jpeg"))],
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["incident_id"] == str(fake_incident.id)
    # Цитата теперь быстрая (случайная из БД) → берётся синхронно и возвращается + пишется
    # на инцидент 2-м коммитом.
    assert body["quote"] == "«цитата» — Автор"
    assert fake_incident.quote == "«цитата» — Автор"
    create.assert_awaited_once()
    kwargs = create.call_args.kwargs
    assert kwargs["region"] == "Самарская область"
    assert kwargs["mno_id"] == mno_id
    assert kwargs["sender_name"] == "Иванов Иван"
    assert len(kwargs["photo_files"]) == 1


@pytest.mark.asyncio
async def test_max_finalize_wrong_token_403(client, monkeypatch):
    """POST /max/finalize с неверным токеном → 403, сервис не вызывается."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    create = AsyncMock()
    with patch(
        "app.api.v1.intake.intake_service.create_incident_from_max_selected",
        new=create,
    ):
        resp = await client.post(
            "/api/v1/intake/max/finalize",
            headers={"X-Intake-Token": "WRONG"},
            data={"sender_name": "X"},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_max_prepare_route_returns_status(client, monkeypatch):
    """POST /max/prepare (токен + JSON) → проксирует dict сервиса; text проброшен."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    prep = AsyncMock(
        return_value={
            "status": "need_address",
            "parsed": {
                "region": "Р",
                "city": "",
                "street": "",
                "coords": "",
                "comment": "",
                "photo_time": "",
            },
        }
    )
    with patch("app.api.v1.intake.intake_service.prepare_max_report", new=prep):
        resp = await client.post(
            "/api/v1/intake/max/prepare",
            headers={"X-Intake-Token": "secret-token"},
            json={"text": "мусор без адреса"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "need_address"
    prep.assert_awaited_once()
    assert prep.call_args.kwargs["text"] == "мусор без адреса"


@pytest.mark.asyncio
async def test_max_prepare_wrong_token_403(client, monkeypatch):
    """POST /max/prepare без валидного токена → 403, сервис не вызывается."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    prep = AsyncMock()
    with patch("app.api.v1.intake.intake_service.prepare_max_report", new=prep):
        resp = await client.post(
            "/api/v1/intake/max/prepare",
            headers={"X-Intake-Token": "WRONG"},
            json={"text": "x"},
        )
    assert resp.status_code == 403
    prep.assert_not_awaited()


# --------------------------------------------------------------------------- #
# OpenStreetMap-рендер карты выбора МНО: _deg2num / _pick_zoom / render_max_map #
# + GET /intake/max/map                                                        #
# --------------------------------------------------------------------------- #


def _png_tile(size=(256, 256), color=(200, 220, 200)) -> bytes:
    """Валидный PNG-тайл, сгенерированный Pillow (замена реальной загрузки тайла)."""
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


_PNG_TILE = _png_tile()


class _TileResp:
    """Фейковый httpx-ответ тайла: .content + .raise_for_status (бросает при ok=False)."""

    def __init__(self, content: bytes, ok: bool = True):
        self.content = content
        self._ok = ok

    def raise_for_status(self):
        if not self._ok:
            raise RuntimeError("non-2xx tile")


def _tile_client_factory(mode: str):
    """Класс фейкового httpx.AsyncClient: mode = all_ok | one_fail | all_fail.

    render_max_map создаёт ОДИН клиент и зовёт .get на каждый тайл — instance-счётчик
    в 'one_fail' роняет ровно первый тайл. Реальная сеть НЕ дёргается.
    """

    class _TileClient:
        def __init__(self, *a, **k):
            self.n = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            self.n += 1
            if mode == "all_fail":
                return _TileResp(b"", ok=False)
            if mode == "one_fail":
                return _TileResp(_PNG_TILE, ok=(self.n != 1))
            return _TileResp(_PNG_TILE, ok=True)

    return _TileClient


def test_deg2num_known_values():
    """_deg2num: детерминированные тайловые координаты (центр Москвы, z=13)."""
    x, y = _deg2num(55.75, 37.62, 13)
    # Целая часть — номер тайла; проверяем и floor, и дробное значение.
    assert int(x) == 4952
    assert int(y) == 2561
    assert x == pytest.approx(4952.064, abs=1e-2)
    assert y == pytest.approx(2561.0748, abs=1e-2)


def test_deg2num_latitude_clamp():
    """_deg2num: широта за пределами проекции (~±85.05°) клэмпится (tan не взрывается)."""
    # Севернее предела → тот же y, что и на самом пределе.
    _, y_over_n = _deg2num(89.0, 10.0, 5)
    _, y_lim_n = _deg2num(85.05112878, 10.0, 5)
    assert y_over_n == pytest.approx(y_lim_n, abs=1e-6)
    # Южнее предела → тот же y, что и на нижнем пределе.
    _, y_over_s = _deg2num(-89.0, 10.0, 5)
    _, y_lim_s = _deg2num(-85.05112878, 10.0, 5)
    assert y_over_s == pytest.approx(y_lim_s, abs=1e-6)


def test_pick_zoom_small_bbox_high_zoom():
    """Крошечный bbox → максимальный зум из диапазона."""
    z = _pick_zoom(55.750, 37.620, 55.751, 37.621)
    zmin, zmax = intake_svc._MAP_ZOOM_RANGE
    assert z == zmax


def test_pick_zoom_wide_bbox_low_zoom():
    """Широкий bbox (полстраны) → минимальный зум из диапазона."""
    z = _pick_zoom(40.0, 20.0, 60.0, 120.0)
    zmin, zmax = intake_svc._MAP_ZOOM_RANGE
    assert z == zmin


def test_pick_zoom_degenerate_default():
    """Вырожденный bbox (одна точка) → дефолтный зум 15, в пределах диапазона."""
    z = _pick_zoom(55.75, 37.62, 55.75, 37.62)
    zmin, zmax = intake_svc._MAP_ZOOM_RANGE
    assert z == 15
    assert zmin <= z <= zmax


@pytest.mark.asyncio
async def test_render_max_map_returns_valid_png(monkeypatch):
    """render_max_map: все тайлы ок (мок) → валидный PNG размера _MAP_SIZE, непустой."""
    monkeypatch.setattr(
        intake_svc.httpx, "AsyncClient", _tile_client_factory("all_ok")
    )
    png = await intake_svc.render_max_map((55.7, 37.6), [(55.71, 37.61), (55.72, 37.62)])
    assert png  # непустой
    img = Image.open(BytesIO(png))
    img.load()
    assert img.format == "PNG"
    assert img.size == intake_svc._MAP_SIZE


@pytest.mark.asyncio
async def test_render_max_map_one_tile_fails_still_png(monkeypatch):
    """Один тайл не-2xx → серая дырка, но карта всё равно валидный PNG нужного размера."""
    monkeypatch.setattr(
        intake_svc.httpx, "AsyncClient", _tile_client_factory("one_fail")
    )
    png = await intake_svc.render_max_map((55.7, 37.6), [(55.71, 37.61)])
    img = Image.open(BytesIO(png))
    img.load()
    assert img.format == "PNG"
    assert img.size == intake_svc._MAP_SIZE


@pytest.mark.asyncio
async def test_render_max_map_all_tiles_fail_raises(monkeypatch):
    """Все тайлы сбойны → render_max_map бросает (роутер превратит в 502)."""
    monkeypatch.setattr(
        intake_svc.httpx, "AsyncClient", _tile_client_factory("all_fail")
    )
    with pytest.raises(Exception):
        await intake_svc.render_max_map((55.7, 37.6), [(55.71, 37.61)])


@pytest.mark.asyncio
async def test_max_map_requires_token_403(client, monkeypatch):
    """GET /max/map без X-Intake-Token → 403 (гейт токена)."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    resp = await client.get(
        "/api/v1/intake/max/map", params={"lat": 55.7, "lon": 37.6}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_max_map_returns_png(client, monkeypatch):
    """GET /max/map (токен) → 200 image/png; точка и pts переданы в сервис."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    render = AsyncMock(return_value=b"\x89PNG\r\n\x1a\nDATA")
    with patch("app.api.v1.intake.intake_service.render_max_map", new=render):
        resp = await client.get(
            "/api/v1/intake/max/map",
            headers={"X-Intake-Token": "secret-token"},
            params={"lat": 55.7, "lon": 37.6, "pts": "55.71,37.61;55.72,37.62"},
        )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == b"\x89PNG\r\n\x1a\nDATA"
    render.assert_awaited_once()
    point, pts = render.await_args.args
    assert point == (55.7, 37.6)
    assert pts == [(55.71, 37.61), (55.72, 37.62)]


@pytest.mark.asyncio
async def test_max_map_upstream_error_502(client, monkeypatch):
    """Сбой рендера карты (render_max_map бросает) → 502 MAP_UPSTREAM_ERROR."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    render = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("app.api.v1.intake.intake_service.render_max_map", new=render):
        resp = await client.get(
            "/api/v1/intake/max/map",
            headers={"X-Intake-Token": "secret-token"},
            params={"lat": 55.7, "lon": 37.6},
        )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "MAP_UPSTREAM_ERROR"
