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
from app.models import Incident
from app.services.intake import (
    create_incident_from_form,
    create_incident_from_public_form,
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
# Публичная форма волонтёра: POST /form                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_public_form_creates_incident(client):
    """POST /form с 1 фото → 200 ok + incident_id; сервис вызван с source-полями."""
    fake_incident = Incident(source="form", status="new")
    fake_incident.id = uuid4()
    create = AsyncMock(return_value=fake_incident)

    with patch(
        "app.api.v1.intake.intake_service.create_incident_from_public_form",
        new=create,
    ):
        resp = await client.post(
            "/api/v1/intake/form",
            data={
                "fio": "Иванов Иван",
                "full_address": "Самарская область, г. Самара, ул. Ленина, 1",
                "region": "Самарская область",
                "city": "г. Самара",
                "street": "ул. Ленина, 1",
                "coords": "53.2, 50.1",
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

    create.assert_awaited_once()
    kwargs = create.call_args.kwargs
    assert kwargs["fio"] == "Иванов Иван"
    assert kwargs["region"] == "Самарская область"
    assert len(kwargs["photo_files"]) == 1


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
    """>3 фото → 400 VALIDATION_ERROR (реальный сервис, проверка до записи БД)."""
    files = [
        ("photos", (f"{i}.jpg", BytesIO(_FAKE_IMG), "image/jpeg")) for i in range(4)
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
    assert incident.source == "form"
    assert incident.region == "Самарская область"
    assert incident.city == "г. Самара"
    assert incident.street == "ул. Мира, 5"
    assert incident.bins is False
    assert incident.photo_time is not None and incident.photo_time.tzinfo is not None
    assert incident.photos == 0
    assert incident.photo_urls == []


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
