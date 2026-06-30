"""Тесты МНО — офлайн: эндпоинты с замоканным сервисом + юнит-тесты логики заглушки."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.sql.operators import eq

from app.models import Mno
from app.schemas.mno import MnoCreate, MnoDetail, MnoListItem, MnoSyncResult
from app.services import mno as mno_service
from app.services.mno import _filters


def _item(**kw) -> MnoListItem:
    base = dict(
        id=uuid4(),
        reg="63-04-001162",
        name="Контейнерная площадка, ул. Бульварная, 18",
        region_code="63",
        region_name="Самарская область",
        city="пгт Усть-Кинельский",
        address="Бульварная улица, 18",
        coords="53.231410, 50.166820",
        fgis_id="02e29deb-1aa8-4949-a1c2-8db71252acb6",
        synced=True,
        sync_date=datetime(2026, 4, 26, 6, 30, tzinfo=timezone.utc),
        incidents=1,
    )
    base.update(kw)
    return MnoListItem(**base)


def _detail(**kw) -> MnoDetail:
    return MnoDetail(**_item(**kw).model_dump())


# --- Эндпоинты -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_mno_returns_list(client):
    with patch(
        "app.api.v1.mno.mno_service.list_mno",
        new=AsyncMock(return_value=[_item()]),
    ):
        resp = await client.get("/api/v1/mno")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["region_name"] == "Самарская область"
    assert body[0]["synced"] is True


@pytest.mark.asyncio
async def test_list_mno_forwards_filters(client):
    """region/synced/search/sort пробрасываются в сервис."""
    spy = AsyncMock(return_value=[])
    with patch("app.api.v1.mno.mno_service.list_mno", new=spy):
        resp = await client.get(
            "/api/v1/mno?region=63&synced=false&search=Бульварная&sort=reg&order=desc"
        )
    assert resp.status_code == 200
    kw = spy.call_args.kwargs
    assert kw["region"] == "63"
    assert kw["synced"] is False
    assert kw["search"] == "Бульварная"
    assert kw["sort"] == "reg"
    assert kw["order"] == "desc"


@pytest.mark.asyncio
async def test_create_mno_synced_false(client):
    """POST /mno создаёт несинхронизированное МНО (synced=false, fgis_id=null)."""
    created = _detail(synced=False, fgis_id=None, sync_date=None, incidents=0)
    spy = AsyncMock(return_value=created)
    with patch("app.api.v1.mno.mno_service.create_mno", new=spy):
        resp = await client.post(
            "/api/v1/mno",
            json={
                "name": "Контейнерная площадка, ул. Новая, 1",
                "coords": "53.2, 50.6",
                "region_code": "63",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["synced"] is False
    assert body["fgis_id"] is None
    # Тело передано в сервис как MnoCreate.
    payload = spy.call_args.args[1]
    assert isinstance(payload, MnoCreate)
    assert payload.name == "Контейнерная площадка, ул. Новая, 1"


@pytest.mark.asyncio
async def test_create_mno_requires_name_and_coords(client):
    """Без name/coords → 422 (обязательные поля)."""
    resp = await client.post("/api/v1/mno", json={"city": "г. Кинель"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sync_all_endpoint(client):
    with patch(
        "app.api.v1.mno.mno_service.sync_all",
        new=AsyncMock(return_value=MnoSyncResult(synced=5, total=15)),
    ):
        resp = await client.post("/api/v1/mno/sync")
    assert resp.status_code == 200
    assert resp.json() == {"synced": 5, "total": 15}


@pytest.mark.asyncio
async def test_sync_one_endpoint(client):
    synced = _detail(synced=True, fgis_id="STUB-deadbeef")
    with patch(
        "app.api.v1.mno.mno_service.sync_one",
        new=AsyncMock(return_value=synced),
    ):
        resp = await client.post(f"/api/v1/mno/{synced.id}/sync")
    assert resp.status_code == 200
    body = resp.json()
    assert body["synced"] is True
    assert body["fgis_id"] == "STUB-deadbeef"


@pytest.mark.asyncio
async def test_export_mno_returns_xlsx(client):
    with patch(
        "app.api.v1.mno.mno_service.list_for_export",
        new=AsyncMock(return_value=[]),
    ), patch("app.api.v1.mno.build_mno_xlsx", return_value=b"PK\x03\x04mnoxlsx"):
        resp = await client.get("/api/v1/mno/export")
    assert resp.status_code == 200
    assert resp.content == b"PK\x03\x04mnoxlsx"
    assert (
        resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "filename*=UTF-8''" in resp.headers["content-disposition"]


@pytest.mark.asyncio
async def test_static_export_not_shadowed_by_id(client):
    """GET /mno/export объявлен ДО /{id}: его не перехватывает get_mno."""
    with patch(
        "app.api.v1.mno.mno_service.list_for_export",
        new=AsyncMock(return_value=[]),
    ), patch("app.api.v1.mno.build_mno_xlsx", return_value=b"xlsx"), patch(
        "app.api.v1.mno.mno_service.get_mno",
        new=AsyncMock(side_effect=AssertionError("get_mno перехватил /export")),
    ):
        resp = await client.get("/api/v1/mno/export")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_static_sync_not_shadowed_by_id(client):
    """POST /mno/sync объявлен ДО /{id}/sync: уходит в sync_all, не в sync_one."""
    spy = AsyncMock(return_value=MnoSyncResult(synced=0, total=0))
    with patch("app.api.v1.mno.mno_service.sync_all", new=spy), patch(
        "app.api.v1.mno.mno_service.sync_one",
        new=AsyncMock(side_effect=AssertionError("sync_one перехватил /sync")),
    ):
        resp = await client.post("/api/v1/mno/sync")
    assert resp.status_code == 200
    spy.assert_awaited_once()


# --- _filters ------------------------------------------------------------------


def test_filters_region_exact_match():
    """region → равенство region_code == значение (НЕ ilike)."""
    filters = _filters(None, "63", None)
    assert len(filters) == 1
    clause = filters[0]
    assert clause.operator is eq
    assert clause.right.value == "63"
    assert "ilike" not in str(clause).lower()


def test_filters_synced_bool():
    assert len(_filters(None, None, True)) == 1
    assert len(_filters(None, None, False)) == 1
    # None → фильтра нет
    assert _filters(None, None, None) == []


def test_filters_search_only():
    filters = _filters("Бульварная", None, None)
    assert len(filters) == 1
    # OR из ilike-условий (str() рендерит дефолтным диалектом как LIKE-семейство).
    assert "like" in str(filters[0]).lower()


def test_filters_combine_all():
    assert len(_filters("ул", "63", False)) == 3


def test_filters_blank_region_ignored():
    assert _filters(None, "   ", None) == []


# --- Заглушка синхронизации (юнит) ---------------------------------------------


def _orm_mno(**kw) -> Mno:
    base = dict(
        reg="63-04-001164",
        name="Контейнерная площадка, ул. Спортивная, 4",
        region_code="63",
        city="пгт Усть-Кинельский",
        address="Спортивная улица, 4",
        coords="53.232000, 50.170300",
        fgis_id=None,
        synced=False,
        sync_date=None,
        incidents=1,
    )
    base.update(kw)
    m = Mno(**base)
    m.id = kw.get("id", uuid4())
    return m


@pytest.mark.asyncio
async def test_sync_all_stub_marks_pending():
    """sync_all (заглушка): все не-synced → synced=True, sync_date, fgis_id=STUB-…; счётчики."""
    session = AsyncMock()
    count_res = MagicMock()
    count_res.scalar_one.return_value = 3
    pending = [_orm_mno(), _orm_mno()]
    pending_res = MagicMock()
    pending_res.scalars.return_value.all.return_value = pending
    session.execute = AsyncMock(side_effect=[count_res, pending_res])
    session.add = MagicMock()

    result = await mno_service.sync_all(session, uuid4())

    assert result.synced == 2
    assert result.total == 3
    for m in pending:
        assert m.synced is True
        assert m.sync_date is not None
        assert m.fgis_id is not None and m.fgis_id.startswith("STUB-")
    # Системный аудит записан.
    assert session.add.called


@pytest.mark.asyncio
async def test_sync_one_stub_marks_single():
    """sync_one (заглушка) помечает одно МНО synced+fgis_id+sync_date и отдаёт карточку."""
    mno = _orm_mno()
    get_res = MagicMock()
    get_res.scalar_one_or_none.return_value = mno
    names_res = MagicMock()
    names_res.all.return_value = [("63", "Самарская область")]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[get_res, names_res])
    session.add = MagicMock()

    detail = await mno_service.sync_one(session, mno.id, uuid4())

    assert mno.synced is True
    assert mno.fgis_id.startswith("STUB-")
    assert mno.sync_date is not None
    assert detail.synced is True
    assert detail.region_name == "Самарская область"


@pytest.mark.asyncio
async def test_create_mno_service_sets_defaults():
    """create_mno: synced=False, fgis_id=None, incidents=0; region_name резолвится."""
    added: list = []
    session = AsyncMock()
    session.add = MagicMock(side_effect=lambda o: added.append(o))

    async def _flush():
        for o in added:
            if isinstance(o, Mno) and o.id is None:
                o.id = uuid4()

    session.flush = AsyncMock(side_effect=_flush)
    names_res = MagicMock()
    names_res.all.return_value = [("63", "Самарская область")]
    session.execute = AsyncMock(return_value=names_res)

    data = MnoCreate(name="Площадка X", coords="53.2, 50.6", region_code="63", reg="63-04-009999")
    detail = await mno_service.create_mno(session, data, uuid4())

    assert detail.synced is False
    assert detail.fgis_id is None
    assert detail.incidents == 0
    assert detail.region_name == "Самарская область"
