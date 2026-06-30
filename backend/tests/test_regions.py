"""Тесты «Регионы» и федеральных округов — офлайн."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.errors import ConflictError
from app.models import Region
from app.schemas.region import RegionCreate, RegionDetail, RegionListItem
from app.services import region as region_service


def _item(**kw) -> RegionListItem:
    base = dict(
        code="63",
        name="Самарская область",
        fed=5,
        fed_code="ПФО",
        fed_name="Приволжский",
        operators=["ЭкоСтройРесурс"],
        active=True,
        last_sync=None,
        mno_count=9,
        incidents_count=6,
    )
    base.update(kw)
    return RegionListItem(**base)


# --- Эндпоинты -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_regions_returns_counts(client):
    with patch(
        "app.api.v1.regions.region_service.list_regions",
        new=AsyncMock(return_value=[_item()]),
    ):
        resp = await client.get("/api/v1/regions")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["mno_count"] == 9
    assert body[0]["incidents_count"] == 6
    assert body[0]["fed_code"] == "ПФО"


@pytest.mark.asyncio
async def test_list_regions_forwards_fed_filter(client):
    """fed передаётся списком int, search/sort/order — тоже."""
    spy = AsyncMock(return_value=[])
    with patch("app.api.v1.regions.region_service.list_regions", new=spy):
        resp = await client.get("/api/v1/regions?fed=2&fed=5&search=обл&sort=name&order=desc")
    assert resp.status_code == 200
    kw = spy.call_args.kwargs
    assert kw["fed"] == [2, 5]
    assert kw["search"] == "обл"
    assert kw["sort"] == "name"
    assert kw["order"] == "desc"


@pytest.mark.asyncio
async def test_get_region_by_code(client):
    detail = RegionDetail(**_item(code="77", name="Москва", fed=1, fed_code="ЦФО", fed_name="Центральный").model_dump())
    with patch(
        "app.api.v1.regions.region_service.get_region",
        new=AsyncMock(return_value=detail),
    ):
        resp = await client.get("/api/v1/regions/77")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Москва"


@pytest.mark.asyncio
async def test_create_region_with_operators(client):
    """POST /regions с несколькими операторами → active=true, операторы переданы."""
    created = RegionDetail(
        **_item(
            code="74",
            name="Челябинская область",
            fed=6,
            fed_code="УФО",
            fed_name="Уральский",
            operators=["Центр коммунального сервиса", "Горэкоцентр"],
            mno_count=0,
            incidents_count=0,
        ).model_dump()
    )
    spy = AsyncMock(return_value=created)
    with patch("app.api.v1.regions.region_service.create_region", new=spy):
        resp = await client.post(
            "/api/v1/regions",
            json={
                "code": "74",
                "name": "Челябинская область",
                "fed": 6,
                "operators": ["Центр коммунального сервиса", "Горэкоцентр"],
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["active"] is True
    assert body["operators"] == ["Центр коммунального сервиса", "Горэкоцентр"]
    payload = spy.call_args.args[1]
    assert isinstance(payload, RegionCreate)
    assert payload.operators == ["Центр коммунального сервиса", "Горэкоцентр"]


# --- Федеральные округа --------------------------------------------------------


@pytest.mark.asyncio
async def test_federal_districts_returns_eight(client):
    """GET /federal-districts → 8 округов из константы (НЕ мок)."""
    resp = await client.get("/api/v1/federal-districts")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 8
    assert body[0] == {"id": 1, "code": "ЦФО", "name": "Центральный"}
    assert body[-1] == {"id": 8, "code": "ДФО", "name": "Дальневосточный"}


# --- Сервис: подсчёты mno_count/incidents_count --------------------------------


def _orm_region(**kw) -> Region:
    base = dict(
        code="63",
        name="Самарская область",
        fed=5,
        operators=["ЭкоСтройРесурс"],
        active=True,
        last_sync=None,
    )
    base.update(kw)
    return Region(**base)


@pytest.mark.asyncio
async def test_list_regions_service_counts():
    """list_regions считает mno_count по region_code и incidents_count по имени региона."""
    regions = [
        _orm_region(code="63", name="Самарская область", fed=5),
        _orm_region(code="51", name="Мурманская область", fed=2, operators=[]),
    ]
    regions_res = MagicMock()
    regions_res.scalars.return_value.all.return_value = regions
    mno_res = MagicMock()
    mno_res.all.return_value = [("63", 9)]
    inc_res = MagicMock()
    inc_res.all.return_value = [("Самарская область", 6)]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[regions_res, mno_res, inc_res])

    items = await region_service.list_regions(session)
    by_code = {i.code: i for i in items}

    assert by_code["63"].mno_count == 9
    assert by_code["63"].incidents_count == 6
    assert by_code["63"].fed_code == "ПФО"
    assert by_code["63"].fed_name == "Приволжский"
    # Регион без МНО/обращений → нули.
    assert by_code["51"].mno_count == 0
    assert by_code["51"].incidents_count == 0


@pytest.mark.asyncio
async def test_create_region_service_active_true():
    """create_region: active=True, операторы сохранены, дубликата нет."""
    dup_res = MagicMock()
    dup_res.scalar_one_or_none.return_value = None
    mno_res = MagicMock()
    mno_res.all.return_value = []
    inc_res = MagicMock()
    inc_res.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[dup_res, mno_res, inc_res])
    session.add = MagicMock()

    data = RegionCreate(code="74", name="Челябинская область", fed=6, operators=["ЦКС", "Горэкоцентр"])
    detail = await region_service.create_region(session, data, uuid4())

    assert detail.active is True
    assert detail.operators == ["ЦКС", "Горэкоцентр"]
    assert detail.fed_code == "УФО"


@pytest.mark.asyncio
async def test_create_region_duplicate_code_conflict():
    """Дубликат кода → ConflictError (409)."""
    dup_res = MagicMock()
    dup_res.scalar_one_or_none.return_value = _orm_region(code="63")
    session = AsyncMock()
    session.execute = AsyncMock(return_value=dup_res)

    with pytest.raises(ConflictError):
        await region_service.create_region(
            session, RegionCreate(code="63", name="Дубль", fed=5), uuid4()
        )
