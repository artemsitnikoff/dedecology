"""Тесты раздела «Интеграция ФГИС» — офлайн (httpx/сессия мокаются).

Покрытие:
  - JSONP-парсер (снятие обёртки, пустой/битый ответ);
  - split_bbox_2x2;
  - краулер enumerate_region_mno_ids (дробление большого кластера + сбор без дублей,
    фолбэк на MAX_Z);
  - REGION_FED (значения 1..8, типовые коды);
  - sync_regions (id→code, сохранение operators/active при update);
  - require_superadmin (ForbiddenError для не-суперадмина);
  - эндпоинты /integration с замоканным сервисом.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.core.errors import AppError, ForbiddenError
from app.core.permissions import require_superadmin
from app.models import Region, User
from app.schemas.integration import (
    IntegrationOverview,
    MnoOverview,
    MnoSyncStatus,
    RegionsOverview,
    RegionsSyncResult,
)
from app.services import fgis, mno_sync
from app.services.fgis import parse_jsonp, split_bbox_2x2
from app.services.region_fed import REGION_FED, region_fed


# --- JSONP-парсер --------------------------------------------------------------


def test_parse_jsonp_unwraps_callback():
    text = 'callback({"type":"FeatureCollection","features":[{"properties":{"id":"abc"}}]});'
    data = parse_jsonp(text)
    assert data["type"] == "FeatureCollection"
    assert data["features"][0]["properties"]["id"] == "abc"


def test_parse_jsonp_unwraps_without_semicolon():
    text = 'callback({"features":[]})'
    assert parse_jsonp(text)["features"] == []


def test_parse_jsonp_empty_features():
    text = 'callback({"type":"FeatureCollection","features":[]});'
    assert parse_jsonp(text)["features"] == []


def test_parse_jsonp_blank_returns_empty_collection():
    assert parse_jsonp("")["features"] == []
    assert parse_jsonp("   ")["features"] == []


def test_parse_jsonp_garbage_degrades():
    # Битый JSON внутри обёртки → пустая коллекция, без исключения.
    assert parse_jsonp("callback(not-json);")["features"] == []


def test_split_bbox_2x2():
    subs = split_bbox_2x2((0, 0, 10, 20))
    assert len(subs) == 4
    assert (0, 0, 5, 10) in subs
    assert (5, 10, 10, 20) in subs


# --- Краулер enumerate_region_mno_ids ------------------------------------------


@pytest.mark.asyncio
async def test_crawler_splits_big_cluster_and_dedups(monkeypatch):
    """Большой кластер (iconContent>100) дробится 2×2; малые кластеры и одиночки
    собираются без дублей; обрезанные id большого кластера НЕ попадают в выборку."""
    # Один стартовый цель-квадрат, чтобы обход был детерминированным.
    monkeypatch.setattr(fgis, "START_CELLS", [(0, 0, 10, 10)])
    monkeypatch.setattr(fgis, "START_Z", 4)

    calls: list = []

    async def fake_fetch_tile(filter_id, bbox, z):
        calls.append((bbox, z))
        n = len(calls)
        if n == 1:
            # Большой кластер: total=250 > 100, z=4 < MAX_Z → должен раздробиться,
            # обрезанные "x*" в выборку НЕ идут.
            return [
                {
                    "properties": {
                        "layer": 5,
                        "ids": [f"x{i}" for i in range(100)],
                        "iconContent": "250",
                    }
                }
            ]
        # 4 подъячейки: одиночка + общий id (дедуп) + малый кластер + общий cluster-id.
        return [
            {"properties": {"layer": 5, "id": f"single-{n}"}},
            {"properties": {"layer": 5, "id": "SHARED"}},
            {"properties": {"layer": 5, "ids": [f"c{n}", "SHARED-CL"], "iconContent": "2"}},
        ]

    monkeypatch.setattr(fgis, "fetch_tile", fake_fetch_tile)

    ids, issues = await fgis.enumerate_region_mno_ids("filter-uuid", 51)

    # 1 стартовая ячейка + 4 подъячейки = 5 tile-запросов.
    assert len(calls) == 5
    # Подъячейки ушли на зум START_Z+2 = 6.
    assert all(z == 6 for _bbox, z in calls[1:])
    # Обрезанные id большого кластера НЕ добавлены (кластер раздроблён, не взят).
    assert "x0" not in ids
    # Собрано: single-2..single-5 (4) + SHARED (1) + c2..c5 (4) + SHARED-CL (1) = 10.
    assert ids == {
        "single-2", "single-3", "single-4", "single-5",
        "SHARED", "c2", "c3", "c4", "c5", "SHARED-CL",
    }
    assert len(ids) == 10  # дубли SHARED/SHARED-CL схлопнуты
    assert issues == []


@pytest.mark.asyncio
async def test_crawler_maxz_fallback_takes_truncated(monkeypatch):
    """На MAX_Z большой кластер не дробится — берём обрезанные id + запись в issues."""
    monkeypatch.setattr(fgis, "START_CELLS", [(0, 0, 10, 10)])
    monkeypatch.setattr(fgis, "START_Z", fgis.MAX_Z)  # стартуем уже на макс. зуме

    async def fake_fetch_tile(filter_id, bbox, z):
        return [
            {"properties": {"layer": 5, "ids": ["a", "b", "c"], "iconContent": "500"}}
        ]

    monkeypatch.setattr(fgis, "fetch_tile", fake_fetch_tile)

    ids, issues = await fgis.enumerate_region_mno_ids("f", 51)
    assert ids == {"a", "b", "c"}
    assert len(issues) == 1
    assert "макс" in issues[0].lower()


@pytest.mark.asyncio
async def test_crawler_progress_callback(monkeypatch):
    monkeypatch.setattr(fgis, "START_CELLS", [(0, 0, 10, 10)])
    monkeypatch.setattr(fgis, "START_Z", 4)

    async def fake_fetch_tile(filter_id, bbox, z):
        return [{"properties": {"layer": 5, "id": "one"}}]

    monkeypatch.setattr(fgis, "fetch_tile", fake_fetch_tile)

    seen: list = []
    ids, _ = await fgis.enumerate_region_mno_ids(
        "f", 51, on_progress=lambda n: seen.append(n)
    )
    assert ids == {"one"}
    assert seen and seen[-1] == 1


# --- REGION_FED ----------------------------------------------------------------


def test_region_fed_values_in_range():
    assert REGION_FED  # непустая
    assert all(1 <= v <= 8 for v in REGION_FED.values())


def test_region_fed_known_codes():
    assert region_fed("51") == 2   # Мурманская → СЗФО
    assert region_fed("63") == 5   # Самарская → ПФО
    assert region_fed("77") == 1   # Москва → ЦФО
    assert region_fed("74") == 6   # Челябинская → УФО


def test_region_fed_unknown_is_zero():
    assert region_fed("999") == 0
    assert region_fed("") == 0


def test_region_fed_single_digit_normalized():
    # ФГИС может прислать id=1 (Адыгея) → "01" в ЮФО(3).
    assert region_fed("1") == 3
    assert region_fed("5") == 4  # Дагестан "05" → СКФО


# --- sync_regions --------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_regions_maps_id_to_code_and_preserves_operators(monkeypatch):
    """id→code=str(id), fed из карты; при update operators/active НЕ трогаются."""
    monkeypatch.setattr(
        fgis,
        "fetch_regions",
        AsyncMock(
            return_value=[
                {"id": 51, "name": "Мурманская область"},
                {"id": 63, "name": "Самарская область"},
            ]
        ),
    )

    # 51 — новый (insert); 63 — существующий (update, operators/active сохранить).
    existing_63 = Region(
        code="63", name="Старое имя", fed=0,
        operators=["ЭкоСтройРесурс"], active=False, last_sync=None,
    )
    sel_51 = MagicMock()
    sel_51.scalar_one_or_none.return_value = None
    sel_63 = MagicMock()
    sel_63.scalar_one_or_none.return_value = existing_63

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[sel_51, sel_63])
    session.add = MagicMock()

    result = await mno_sync.sync_regions(session)

    assert isinstance(result, RegionsSyncResult)
    assert result.total == 2
    assert result.created == 1
    assert result.updated == 1
    assert result.last_sync is not None

    # Существующий обновлён по name/fed/last_sync, но operators/active сохранены.
    assert existing_63.name == "Самарская область"
    assert existing_63.fed == 5
    assert existing_63.last_sync is not None
    assert existing_63.operators == ["ЭкоСтройРесурс"]
    assert existing_63.active is False

    # Новый регион вставлен с корректным кодом/округом и active=True.
    inserted = session.add.call_args.args[0]
    assert isinstance(inserted, Region)
    assert inserted.code == "51"
    assert inserted.fed == 2
    assert inserted.active is True
    assert inserted.operators == []


# --- require_superadmin --------------------------------------------------------


def _user(is_superadmin: bool) -> User:
    u = User(
        email="x@y.z", password_hash="h", fio="U", role="admin",
        status="active", is_active=True, is_superadmin=is_superadmin,
    )
    u.id = uuid4()
    return u


@pytest.mark.asyncio
async def test_require_superadmin_forbids_non_super():
    with pytest.raises(ForbiddenError):
        await require_superadmin(_user(is_superadmin=False))


@pytest.mark.asyncio
async def test_require_superadmin_allows_super():
    assert await require_superadmin(_user(is_superadmin=True)) is None


# --- Эндпоинты (мок сервиса) ---------------------------------------------------


@pytest.mark.asyncio
async def test_overview_endpoint(client):
    ov = IntegrationOverview(
        regions=RegionsOverview(total=89, last_sync=None),
        mno=MnoOverview(total=1234),
        per_region=[],
    )
    with patch("app.api.v1.integration.mno_sync.overview", new=AsyncMock(return_value=ov)):
        resp = await client.get("/api/v1/integration/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["regions"]["total"] == 89
    assert body["mno"]["total"] == 1234


@pytest.mark.asyncio
async def test_regions_sync_endpoint(client, fake_session):
    result = RegionsSyncResult(total=89, created=89, updated=0, last_sync="2026-07-01T10:00:00Z")
    with patch(
        "app.api.v1.integration.mno_sync.sync_regions",
        new=AsyncMock(return_value=result),
    ):
        resp = await client.post("/api/v1/integration/regions/sync")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 89
    assert body["created"] == 89
    # роутер коммитит.
    fake_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_start_mno_sync_endpoint(client):
    region = Region(code="51", name="Мурманская область", fed=2, operators=[], active=True)
    job = mno_sync.MnoSyncJob(job_id="job-123", region_code="51", region_name="Мурманская область")
    with patch(
        "app.api.v1.integration.mno_sync.get_region_or_404",
        new=AsyncMock(return_value=region),
    ), patch(
        "app.api.v1.integration.mno_sync.start_mno_sync",
        return_value=job,
    ) as start_spy:
        resp = await client.post("/api/v1/integration/mno/sync", json={"region_code": "51"})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"job_id": "job-123", "region_code": "51", "state": "running"}
    start_spy.assert_called_once_with("51", "Мурманская область")


@pytest.mark.asyncio
async def test_start_mno_sync_unknown_region_404(client):
    with patch(
        "app.api.v1.integration.mno_sync.get_region_or_404",
        new=AsyncMock(side_effect=AppError("REGION_NOT_FOUND", "нет региона", status_code=404)),
    ):
        resp = await client.post("/api/v1/integration/mno/sync", json={"region_code": "99"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "REGION_NOT_FOUND"


@pytest.mark.asyncio
async def test_mno_sync_status_by_job_id(client):
    status = MnoSyncStatus(
        job_id="job-123", region_code="51", region_name="Мурманская область",
        state="done", discovered=42, fetched=42, upserted=40,
        error=None, started_at="2026-07-01T10:00:00Z", finished_at="2026-07-01T10:05:00Z",
    )
    job = mno_sync.MnoSyncJob(job_id="job-123", region_code="51", region_name="Мурманская область")
    with patch(
        "app.api.v1.integration.mno_sync.get_job", return_value=job
    ), patch(
        "app.api.v1.integration.mno_sync.job_to_status", return_value=status
    ):
        resp = await client.get("/api/v1/integration/mno/sync/status?job_id=job-123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "done"
    assert body["discovered"] == 42
    assert body["upserted"] == 40


@pytest.mark.asyncio
async def test_mno_sync_status_not_found_404(client):
    with patch("app.api.v1.integration.mno_sync.get_job", return_value=None):
        resp = await client.get("/api/v1/integration/mno/sync/status?job_id=missing")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# --- Детали МНО: sidebar/object как документированный фолбэк --------------------


def test_object_to_flat_maps_nested_sidebar_object():
    """Вложенный ответ sidebar/object (док §3) → плоская форма sidebar/cluster."""
    obj = {
        "id": "7d257019",
        "name": "Контейнерная площадка",
        "registryNumber": "0000217-03",
        "location": {
            "areaName": "Курумканский муниципальный район",
            "populationName": "Сельское поселение Элэсун",
            "address": "ул. Ленина, 52",
            "coordinates": {"latitude": 54.035044, "longitude": 110.097837},
        },
    }
    flat = fgis._object_to_flat(obj)
    assert flat == {
        "id": "7d257019",
        "name": "Контейнерная площадка",
        "registryNumber": "0000217-03",
        "area": "Курумканский муниципальный район",
        "population": "Сельское поселение Элэсун",
        "address": "ул. Ленина, 52",
        "location": {"latitude": 54.035044, "longitude": 110.097837},
    }


@pytest.mark.asyncio
async def test_cluster_details_falls_back_to_sidebar_object(monkeypatch):
    """Если батч sidebar/cluster недоступен — cluster_details деградирует на
    документированный sidebar/object по одному id и отдаёт ту же плоскую форму."""

    class _BoomClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise httpx.ConnectError("batch недоступен")

    monkeypatch.setattr(fgis.httpx, "AsyncClient", _BoomClient)

    async def _fake_object(mno_id):
        return {
            "id": mno_id,
            "name": "Площадка",
            "registryNumber": "R-1",
            "location": {
                "areaName": "Район",
                "populationName": "Село",
                "address": "ул. Тест, 1",
                "coordinates": {"latitude": 1.5, "longitude": 2.5},
            },
        }

    monkeypatch.setattr(fgis, "sidebar_object", _fake_object)

    out = await fgis.cluster_details(["id-1", "id-2"], region_id=3)
    assert len(out) == 2
    assert out[0]["name"] == "Площадка"
    assert out[0]["address"] == "ул. Тест, 1"
    assert out[0]["area"] == "Район"
    assert out[0]["location"] == {"latitude": 1.5, "longitude": 2.5}
