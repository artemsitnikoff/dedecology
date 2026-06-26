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
    create_incident_from_max,
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
    assert incident.region == "Самарская обл"
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
        "app.services.intake.clean_address", new=fake_clean
    ):
        incident = await create_incident_from_max(
            fake_session,
            text="Нижегородская область, г. Нижний Новгород, улица Сергея Есенина, 38",
            msg_id="m-1",
            sender_name="Иван",
            photo_files=[],
        )

    assert incident.source == "max"
    assert incident.region == "Нижегородская обл"  # DaData
    assert incident.city == "г Нижний Новгород"  # DaData
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
async def test_max_service_saves_msg_url(fake_session):
    """Непустой msg_url сохраняется на инциденте КАК ЕСТЬ (полный https-URL)."""
    _max_session(fake_session)
    url = "https://max.ru/c/-75787158905457/AZ8DNeZnbkM"
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=None)
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
        '"street": "ул. Есенина, 38", "coords": "", "time": "10:28"}\n'
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
async def test_ai_parse_incident_empty_text_skips_cli():
    """Пустой текст → None, CLI вообще не вызывается."""
    from app.services import incident_parse

    cli = AsyncMock(return_value='{"region": "x"}')
    with patch("app.services.incident_parse.claude_cli_complete", new=cli):
        assert await incident_parse.ai_parse_incident("   ") is None
    cli.assert_not_awaited()


# --------------------------------------------------------------------------- #
# Мотивирующая цитата о природе: nature_quote (claude CLI + фолбэк)            #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_nature_quote_falls_back_when_cli_none():
    """claude_cli_complete → None: nature_quote отдаёт непустую цитату из фолбэка."""
    from app.services import quotes as quotes_service

    with patch(
        "app.services.quotes.claude_cli_complete",
        new=AsyncMock(return_value=None),
    ):
        quote = await quotes_service.nature_quote()

    assert isinstance(quote, str)
    assert quote.strip()
    assert quote in quotes_service._FALLBACK


@pytest.mark.asyncio
async def test_nature_quote_uses_cli_result_cleaned():
    """Ответ CLI схлопывается в одну строку и используется как есть."""
    from app.services import quotes as quotes_service

    with patch(
        "app.services.quotes.claude_cli_complete",
        new=AsyncMock(return_value="  «Береги природу»\n  — Иван Иванов  "),
    ):
        quote = await quotes_service.nature_quote()

    assert quote == "«Береги природу» — Иван Иванов"


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
