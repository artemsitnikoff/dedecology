"""Тесты МНО — офлайн: эндпоинты с замоканным сервисом + юнит-тесты логики заглушки."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.sql.operators import eq

from app.models import Mno
from app.schemas.base import Paginated
from app.core.errors import ValidationError
from app.schemas.mno import (
    MnoCreate,
    MnoDetail,
    MnoListItem,
    MnoPoint,
    MnoPointsResponse,
    MnoSyncResult,
    MnoVolunteerCreate,
)
from app.services import mno as mno_service
from app.services.mno import _filters, _to_list_item


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


def _page(items=None, total=1, page=1, page_size=100) -> Paginated[MnoListItem]:
    items = [_item()] if items is None else items
    pages = (total + page_size - 1) // page_size if total > 0 else 0
    return Paginated[MnoListItem](
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


@pytest.mark.asyncio
async def test_list_mno_returns_paginated(client):
    with patch(
        "app.api.v1.mno.mno_service.list_mno",
        new=AsyncMock(return_value=_page(total=1)),
    ):
        resp = await client.get("/api/v1/mno")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 100
    assert len(body["items"]) == 1
    assert body["items"][0]["region_name"] == "Самарская область"
    assert body["items"][0]["synced"] is True


@pytest.mark.asyncio
async def test_list_mno_forwards_filters(client):
    """region/synced/search/sort/page/page_size пробрасываются в сервис."""
    spy = AsyncMock(return_value=_page(items=[], total=0))
    with patch("app.api.v1.mno.mno_service.list_mno", new=spy):
        resp = await client.get(
            "/api/v1/mno?region=63&synced=false&search=Бульварная"
            "&sort=reg&order=desc&page=2&page_size=50"
        )
    assert resp.status_code == 200
    kw = spy.call_args.kwargs
    assert kw["region"] == "63"
    assert kw["synced"] is False
    assert kw["search"] == "Бульварная"
    assert kw["sort"] == "reg"
    assert kw["order"] == "desc"
    assert kw["page"] == 2
    assert kw["page_size"] == 50


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


# --- /points (карта) -----------------------------------------------------------


@pytest.mark.asyncio
async def test_list_points_returns_points(client):
    """GET /mno/points отдаёт points/total/capped и пробрасывает фильтры."""
    points_resp = MnoPointsResponse(
        points=[MnoPoint(id=uuid4(), coords="53.231410, 50.166820", name="Площадка A")],
        total=5000,
        capped=True,
    )
    spy = AsyncMock(return_value=points_resp)
    with patch("app.api.v1.mno.mno_service.list_points", new=spy):
        resp = await client.get("/api/v1/mno/points?region=63&synced=true&search=ул")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5000
    assert body["capped"] is True
    assert len(body["points"]) == 1
    assert body["points"][0]["name"] == "Площадка A"
    assert body["points"][0]["coords"] == "53.231410, 50.166820"
    kw = spy.call_args.kwargs
    assert kw["region"] == "63"
    assert kw["synced"] is True
    assert kw["search"] == "ул"


@pytest.mark.asyncio
async def test_static_points_not_shadowed_by_id(client):
    """GET /mno/points объявлен ДО /{id}: его не перехватывает get_mno."""
    with patch(
        "app.api.v1.mno.mno_service.list_points",
        new=AsyncMock(
            return_value=MnoPointsResponse(points=[], total=0, capped=False)
        ),
    ), patch(
        "app.api.v1.mno.mno_service.get_mno",
        new=AsyncMock(side_effect=AssertionError("get_mno перехватил /points")),
    ):
        resp = await client.get("/api/v1/mno/points")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_points_service_marks_capped():
    """list_points: total из COUNT(*), points из строк с координатами, capped при переполнении."""
    count_res = MagicMock()
    count_res.scalar_one.return_value = mno_service.MAX_POINTS + 10
    row = MagicMock(id=uuid4(), coords="53.2, 50.6")
    row.name = "Площадка A"  # name= в конструкторе MagicMock — служебный, задаём явно
    points_res = MagicMock()
    points_res.all.return_value = [row]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, points_res])

    resp = await mno_service.list_points(session, search=None, region=None, synced=None)

    assert resp.total == mno_service.MAX_POINTS + 10
    assert resp.capped is True
    assert len(resp.points) == 1
    assert resp.points[0].name == "Площадка A"
    assert resp.points[0].coords == "53.2, 50.6"


@pytest.mark.asyncio
async def test_list_points_applies_bbox_filter():
    """Валидный bbox → числовой lat/lon-фильтр в WHERE (COUNT и выборка точек)."""
    count_res = MagicMock()
    count_res.scalar_one.return_value = 1
    row = MagicMock(id=uuid4(), coords="53.2, 50.6")
    row.name = "Площадка A"
    points_res = MagicMock()
    points_res.all.return_value = [row]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, points_res])

    resp = await mno_service.list_points(
        session, search=None, region=None, synced=None, bbox="53.0,50.0,54.0,51.0"
    )

    assert resp.total == 1
    count_sql = str(session.execute.call_args_list[0].args[0])
    points_sql = str(session.execute.call_args_list[1].args[0])
    for sql in (count_sql, points_sql):
        assert "mno.lat IS NOT NULL" in sql
        assert "mno.lat BETWEEN" in sql
        assert "mno.lon BETWEEN" in sql
    # bbox-режим не использует прежний фильтр coords != '' (COUNT его не селектит).
    assert "mno.coords" not in count_sql


@pytest.mark.asyncio
async def test_list_points_bbox_ignored_when_invalid():
    """Битый bbox → игнор: прежнее поведение (coords != '', без lat/lon-фильтра)."""
    count_res = MagicMock()
    count_res.scalar_one.return_value = 0
    points_res = MagicMock()
    points_res.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, points_res])

    await mno_service.list_points(
        session, search=None, region=None, synced=None, bbox="garbage"
    )

    points_sql = str(session.execute.call_args_list[1].args[0])
    assert "mno.coords !=" in points_sql
    assert "BETWEEN" not in points_sql


# --- list_form_points (публичная карта формы /intake/mno-points) ---------------


@pytest.mark.asyncio
async def test_list_form_points_requires_bbox():
    """Без bbox → пусто и БД НЕ трогаем (не тянем весь реестр в публичный эндпоинт)."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=AssertionError("БД не должна вызываться"))

    resp = await mno_service.list_form_points(session, bbox="")

    assert resp.points == []
    assert resp.total == 0
    assert resp.capped is False
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_list_form_points_bbox_garbage_empty():
    """Битый bbox → трактуется как «не задан» → пусто, без обращения к БД."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=AssertionError("БД не должна вызываться"))

    resp = await mno_service.list_form_points(session, bbox="garbage")

    assert resp.points == []
    assert resp.total == 0
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_list_form_points_applies_bbox_and_returns_fields():
    """Валидный bbox → lat/lon-фильтр; точки несут reg/address/name/coords/region/city."""
    count_res = MagicMock()
    count_res.scalar_one.return_value = 1
    row = MagicMock(
        id=uuid4(),
        coords="53.231410, 50.166820",
        reg="63-04-001162",
        address="Бульварная улица, 18",
        city="Самара",
        region_name="Самарская область",  # из LEFT JOIN Region по region_code
    )
    row.name = "Площадка A"  # name= в конструкторе MagicMock служебный — задаём явно
    points_res = MagicMock()
    points_res.all.return_value = [row]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, points_res])

    resp = await mno_service.list_form_points(session, bbox="53.0,50.0,54.0,51.0")

    assert resp.total == 1
    assert resp.capped is False
    assert len(resp.points) == 1
    point = resp.points[0]
    assert point.reg == "63-04-001162"
    assert point.address == "Бульварная улица, 18"
    assert point.name == "Площадка A"
    assert point.coords == "53.231410, 50.166820"
    assert point.region == "Самарская область"
    assert point.city == "Самара"
    # Оба запроса (COUNT и выборка) фильтруют по числовым lat/lon.
    count_sql = str(session.execute.call_args_list[0].args[0])
    points_sql = str(session.execute.call_args_list[1].args[0])
    for sql in (count_sql, points_sql):
        assert "mno.lat IS NOT NULL" in sql
        assert "mno.lat BETWEEN" in sql
        assert "mno.lon BETWEEN" in sql


@pytest.mark.asyncio
async def test_list_form_points_caps_at_limit():
    """total > FORM_MAX_POINTS → capped=True (пользователю стоит приблизить карту)."""
    count_res = MagicMock()
    count_res.scalar_one.return_value = mno_service.FORM_MAX_POINTS + 3
    points_res = MagicMock()
    points_res.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, points_res])

    resp = await mno_service.list_form_points(session, bbox="53.0,50.0,54.0,51.0")

    assert resp.total == mno_service.FORM_MAX_POINTS + 3
    assert resp.capped is True


# --- _filters ------------------------------------------------------------------


def test_filters_region_exact_match():
    """region → равенство region_code == значение (НЕ ilike)."""
    filters = _filters(None, "63", None)
    assert len(filters) == 1
    clause = filters[0]
    assert clause.operator is eq
    assert clause.right.value == "63"
    assert "ilike" not in str(clause).lower()


def test_filters_source_exact_match():
    """source → равенство Mno.source == значение (раздел «Новые МНО» = 'volunteer')."""
    filters = _filters(None, None, None, source="volunteer")
    assert len(filters) == 1
    clause = filters[0]
    assert clause.operator is eq
    assert clause.right.value == "volunteer"
    # Пусто/None → фильтра источника нет.
    assert _filters(None, None, None, source=None) == []
    assert _filters(None, None, None, source="  ") == []


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


# --- #18 многословный поиск (токенизация, AND по токенам) ----------------------


def test_search_clause_single_token_backward_compatible():
    """Один токен → одна OR-группа ilike (прежнее поведение)."""
    clause = mno_service._search_clause("Бульварная")
    sql = str(clause).lower()
    # Ровно одна ilike-группа: несколько LIKE через OR, но без внешнего AND.
    assert sql.count("like") == 6  # name/reg/city/address/coords/fgis_id
    assert " and " not in sql


def test_search_clause_multiword_builds_and_of_or_groups():
    """«Самарская Кинель» → AND из двух OR-групп (каждый токен ищется по всем полям)."""
    clause = mno_service._search_clause("Самарская Кинель")
    sql = str(clause).lower()
    assert " and " in sql  # токены объединены через AND
    assert sql.count("like") == 12  # 6 полей × 2 токена


def test_search_clause_ignores_commas_and_order():
    """Запятые/порядок слов не важны: «Самарская область, Кинель» → 3 токена (AND)."""
    clause = mno_service._search_clause("Самарская область, Кинель")
    sql = str(clause).lower()
    assert sql.count("like") == 18  # 6 полей × 3 токена


def test_search_clause_blank_returns_none():
    """Только разделители → None (клауза не добавляется в _filters)."""
    assert mno_service._search_clause("   ") is None
    assert mno_service._search_clause(" , ; ") is None


def test_filters_multiword_search_single_and_clause():
    """_filters(«Самарская Кинель») → одна клауза (AND-обёртка токенов), не падает."""
    filters = _filters("Самарская Кинель", None, None)
    assert len(filters) == 1
    assert " and " in str(filters[0]).lower()


# --- #17 серверная сортировка по расстоянию (sort=distance + lat/lon) ----------


@pytest.mark.asyncio
async def test_query_sort_distance_orders_by_distance_nulls_last():
    """sort='distance' + lat/lon → ORDER BY (lat IS NULL, квадрат расстояния, id):
    ближайшие первыми, МНО без числовых координат — в конец."""
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=rows_res)

    await mno_service._query(
        session,
        search=None,
        region=None,
        synced=None,
        sort="distance",
        order="asc",
        offset=0,
        limit=100,
        lat=53.2,
        lon=50.16,
    )

    sql = str(session.execute.call_args.args[0]).lower()
    assert "order by" in sql
    # NULL-координаты уезжают в конец (первый ключ сортировки — mno.lat IS NULL).
    assert "mno.lat is null" in sql
    # Сортировка по квадрату расстояния использует обе координаты.
    assert "mno.lat -" in sql
    assert "mno.lon -" in sql


@pytest.mark.asyncio
async def test_query_sort_distance_without_latlon_falls_back_to_name():
    """sort='distance' БЕЗ lat/lon → мягкий фолбэк на name asc (не 500, без distance-выражений)."""
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=rows_res)

    await mno_service._query(
        session,
        search=None,
        region=None,
        synced=None,
        sort="distance",
        order="asc",
        offset=0,
        limit=100,
    )

    sql = str(session.execute.call_args.args[0]).lower()
    assert "order by mno.name asc" in sql
    # Ни distance-выражения, ни NULLS-LAST-костыля — обычная сортировка по имени.
    assert "mno.lat is null" not in sql


@pytest.mark.asyncio
async def test_list_mno_forwards_latlon_to_query(client):
    """GET /mno?sort=distance&lat&lon → lat/lon доходят до сервиса list_mno."""
    spy = AsyncMock(return_value=_page(items=[], total=0))
    with patch("app.api.v1.mno.mno_service.list_mno", new=spy):
        resp = await client.get(
            "/api/v1/mno?sort=distance&lat=53.2&lon=50.16"
        )
    assert resp.status_code == 200
    kw = spy.call_args.kwargs
    assert kw["sort"] == "distance"
    assert kw["lat"] == 53.2
    assert kw["lon"] == 50.16


# --- Заглушка синхронизации (юнит) ---------------------------------------------


def _orm_mno(**kw) -> Mno:
    base = dict(
        reg="63-04-001164",
        name="Контейнерная площадка, ул. Спортивная, 4",
        region_code="63",
        city="пгт Усть-Кинельский",
        address="Спортивная улица, 4",
        coords="53.232000, 50.170300",
        source="fgis",
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


# --- source (происхождение) + волонтёрское создание (public /intake/mno) --------


def test_to_list_item_passes_source():
    """_to_list_item пробрасывает происхождение МНО (source) в строку/карточку."""
    m = _orm_mno(source="volunteer")
    item = mno_service._to_list_item(m, {"63": "Самарская область"})
    assert item.source == "volunteer"


def _volunteer_session():
    """Fake session: add копит объекты, flush присваивает Mno.id, execute → имена регионов."""
    added: list = []
    session = AsyncMock()
    session.add = MagicMock(side_effect=added.append)

    async def _flush():
        for o in added:
            if isinstance(o, Mno) and o.id is None:
                o.id = uuid4()

    session.flush = AsyncMock(side_effect=_flush)
    names_res = MagicMock()
    names_res.all.return_value = [("63", "Самарская область")]
    session.execute = AsyncMock(return_value=names_res)
    return session, added


@pytest.mark.asyncio
async def test_create_mno_from_volunteer_sets_source_and_defaults():
    """create_mno_from_volunteer: source='volunteer', synced=False, fgis_id=None, reg='',
    incidents=0; числовые lat/lon распарсены; карточка отдаётся с source."""
    session, added = _volunteer_session()
    data = MnoVolunteerCreate(
        name="Площадка волонтёра",
        region_code="63",
        city="г. Самара",
        address="ул. Ленина, 1",
        coords="53.2, 50.6",
    )
    detail = await mno_service.create_mno_from_volunteer(session, data)

    assert detail.source == "volunteer"
    assert detail.synced is False
    assert detail.fgis_id is None
    assert detail.reg == ""
    assert detail.incidents == 0
    assert detail.region_name == "Самарская область"

    created = next(o for o in added if isinstance(o, Mno))
    assert created.source == "volunteer"
    assert created.synced is False
    assert created.fgis_id is None
    assert created.lat == 53.2 and created.lon == 50.6


@pytest.mark.asyncio
async def test_create_mno_from_volunteer_stores_volunteer_id():
    """volunteer_id (автор из приложения) проставляется на МНО; по умолчанию None."""
    vol_id = uuid4()
    session, added = _volunteer_session()
    await mno_service.create_mno_from_volunteer(
        session,
        MnoVolunteerCreate(address="ул. Ленина, 1", coords="53.2, 50.6"),
        volunteer_id=vol_id,
    )
    created = next(o for o in added if isinstance(o, Mno))
    assert created.volunteer_id == vol_id

    # Без volunteer_id (аноним) → NULL.
    session2, added2 = _volunteer_session()
    await mno_service.create_mno_from_volunteer(
        session2, MnoVolunteerCreate(address="ул. Ленина, 1", coords="53.2, 50.6")
    )
    created2 = next(o for o in added2 if isinstance(o, Mno))
    assert created2.volunteer_id is None


@pytest.mark.asyncio
async def test_create_mno_from_volunteer_requires_address_and_coords():
    """Пустые address/coords → ValidationError (400), БД НЕ трогаем."""
    session, added = _volunteer_session()

    with pytest.raises(ValidationError):
        await mno_service.create_mno_from_volunteer(
            session, MnoVolunteerCreate(address="   ", coords="53.2, 50.6")
        )
    with pytest.raises(ValidationError):
        await mno_service.create_mno_from_volunteer(
            session, MnoVolunteerCreate(address="ул. Ленина, 1", coords="")
        )
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_mno_from_volunteer_garbage_coords_null_latlon():
    """Мусорные (не-числовые) coords → lat/lon=None, но МНО всё равно создаётся."""
    session, added = _volunteer_session()
    data = MnoVolunteerCreate(address="ул. Ленина, 1", coords="это не координаты")
    detail = await mno_service.create_mno_from_volunteer(session, data)

    created = next(o for o in added if isinstance(o, Mno))
    assert created.lat is None and created.lon is None
    assert detail.source == "volunteer"


@pytest.mark.asyncio
async def test_create_mno_from_volunteer_truncates_overlong_fields():
    """Сверхдлинные поля отсекаются под ширину колонок (нет DataError на INSERT)."""
    session, added = _volunteer_session()
    data = MnoVolunteerCreate(
        name="н" * 600,
        region_code="6" * 20,
        city="г" * 400,
        address="ул. Ленина, 1",
        coords="5" * 200,  # без запятой → lat/lon=None, но непусто → проходит валидацию
    )
    await mno_service.create_mno_from_volunteer(session, data)

    created = next(o for o in added if isinstance(o, Mno))
    assert len(created.name) == 500
    assert len(created.region_code) == 8
    assert len(created.city) == 255
    assert len(created.coords) == 64


@pytest.mark.asyncio
async def test_create_mno_from_volunteer_comment_truncated_and_none():
    """comment: >500 обрезается до 500 и отдаётся в карточке; пустой/пробельный → NULL."""
    # Длинный комментарий → обрезка до 500.
    session, added = _volunteer_session()
    detail = await mno_service.create_mno_from_volunteer(
        session,
        MnoVolunteerCreate(address="ул. Ленина, 1", coords="53.2, 50.6", comment="к" * 600),
    )
    created = next(o for o in added if isinstance(o, Mno))
    assert len(created.comment) == 500
    assert detail.comment == created.comment
    assert detail.photo_urls == []  # без фото — пустой список

    # Пробельный комментарий → NULL (не пустая строка).
    session2, added2 = _volunteer_session()
    detail2 = await mno_service.create_mno_from_volunteer(
        session2,
        MnoVolunteerCreate(address="ул. Ленина, 1", coords="53.2, 50.6", comment="   "),
    )
    created2 = next(o for o in added2 if isinstance(o, Mno))
    assert created2.comment is None
    assert detail2.comment is None


# --- Живой счётчик обращений (incidents = COUNT инцидентов по mno_id) -----------


@pytest.mark.asyncio
async def test_incident_counts_empty_ids_skips_db():
    """Пустой набор id → {} без обращения к БД (не считаем впустую)."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=AssertionError("БД не должна вызываться"))
    assert await mno_service._incident_counts(session, []) == {}
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_incident_counts_builds_map_grouped_by_mno_id():
    """_incident_counts → {mno_id: COUNT}; SQL группирует по incidents.mno_id."""
    id1, id2 = uuid4(), uuid4()
    res = MagicMock()
    res.all.return_value = [(id1, 2), (id2, 5)]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=res)

    counts = await mno_service._incident_counts(session, [id1, id2])

    assert counts == {id1: 2, id2: 5}
    sql = str(session.execute.call_args.args[0]).lower()
    assert "count(incidents.id)" in sql
    assert "group by incidents.mno_id" in sql
    assert "incidents.mno_id in" in sql


@pytest.mark.asyncio
async def test_list_mno_incidents_is_live_count():
    """list_mno: incidents ПЕРЕКРЫВАЕТ статичное поле модели живым COUNT по mno_id."""
    mno = _orm_mno(incidents=99)  # статичное значение — должно быть перекрыто
    count_res = MagicMock()
    count_res.scalar_one.return_value = 1
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = [mno]
    names_res = MagicMock()
    names_res.all.return_value = [("63", "Самарская область")]
    counts_res = MagicMock()
    counts_res.all.return_value = [(mno.id, 3)]
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[count_res, rows_res, names_res, counts_res]
    )

    page = await mno_service.list_mno(session)

    assert page.items[0].incidents == 3  # живой COUNT, НЕ 99


@pytest.mark.asyncio
async def test_list_mno_incidents_zero_when_no_references():
    """МНО без обращений (нет в счётчике) → incidents=0, а не статичное поле модели."""
    mno = _orm_mno(incidents=99)
    count_res = MagicMock()
    count_res.scalar_one.return_value = 1
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = [mno]
    names_res = MagicMock()
    names_res.all.return_value = [("63", "Самарская область")]
    counts_res = MagicMock()
    counts_res.all.return_value = []  # ни один инцидент не ссылается
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[count_res, rows_res, names_res, counts_res]
    )

    page = await mno_service.list_mno(session)

    assert page.items[0].incidents == 0


@pytest.mark.asyncio
async def test_get_mno_incidents_is_live_count():
    """get_mno (деталь): incidents = живой COUNT инцидентов по ссылке mno_id."""
    mno = _orm_mno(incidents=99)
    get_res = MagicMock()
    get_res.scalar_one_or_none.return_value = mno
    names_res = MagicMock()
    names_res.all.return_value = [("63", "Самарская область")]
    counts_res = MagicMock()
    counts_res.all.return_value = [(mno.id, 5)]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[get_res, names_res, counts_res])

    detail = await mno_service.get_mno(session, mno.id)

    assert detail.incidents == 5


@pytest.mark.asyncio
async def test_query_sort_incidents_orders_by_live_count():
    """sort='incidents' → ORDER BY по коррелированному COUNT(incidents.id) WHERE
    incidents.mno_id = mno.id, а НЕ по статичной колонке mno.incidents (та дрейфует)."""
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=rows_res)

    await mno_service._query(
        session,
        search=None,
        region=None,
        synced=None,
        sort="incidents",
        order="desc",
        offset=0,
        limit=100,
    )

    sql = str(session.execute.call_args.args[0]).lower()
    assert "count(incidents.id)" in sql
    assert "incidents.mno_id = mno.id" in sql
    assert "order by" in sql
    # По статичной колонке mno.incidents НЕ сортируем.
    assert "order by mno.incidents" not in sql


def test_filters_bbox_adds_latlon_clauses():
    """bbox в списке /mno → фильтр по числовым lat/lon (отдаём МНО кадра, как /mno/points);
    без bbox / мусор → фильтров нет (прежнее поведение)."""
    assert mno_service._filters(None, None, None, None) == []
    assert mno_service._filters(None, None, None, "мусор") == []
    box = mno_service._filters(None, None, None, "53.0,50.0,54.0,51.0")
    sql = " ".join(str(c) for c in box)
    assert "mno.lat IS NOT NULL" in sql
    assert "mno.lat BETWEEN" in sql
    assert "mno.lon BETWEEN" in sql


@pytest.mark.asyncio
async def test_create_mno_by_volunteer_marks_source(client):
    """POST /mno ВОЛОНТЁРОМ доступен → create_mno зовётся с source='volunteer' и
    actor_user_id=None (создатель не пользователь админки). Админ-создание — source='fgis'."""
    from app.deps import get_current_actor
    from app.main import app
    from app.models import Volunteer

    app.dependency_overrides[get_current_actor] = lambda: Volunteer(id=uuid4())
    created = _detail(source="volunteer", synced=False, fgis_id=None, sync_date=None, incidents=0)
    spy = AsyncMock(return_value=created)
    with patch("app.api.v1.mno.mno_service.create_mno", new=spy):
        resp = await client.post("/api/v1/mno", json={"name": "Новая", "coords": "55, 83"})
    assert resp.status_code == 201
    assert resp.json()["source"] == "volunteer"
    # actor_user_id (3-й позиционный) = None, source='volunteer' (kwarg).
    assert spy.call_args.args[2] is None
    assert spy.call_args.kwargs.get("source") == "volunteer"


# --- list_by_volunteer — «Мои МНО» (фильтр по volunteer_id, свежие первыми) -----


@pytest.mark.asyncio
async def test_mno_list_by_volunteer_filters_and_builds_detail():
    """list_by_volunteer (МНО): WHERE mno.volunteer_id + ORDER BY created_at DESC;
    строки собираются в MnoDetail с живым COUNT обращений и region_name."""
    vol_id = uuid4()
    mno = _orm_mno(source="volunteer")
    count_res = MagicMock()
    count_res.scalar_one.return_value = 1
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = [mno]
    names_res = MagicMock()
    names_res.all.return_value = [("63", "Самарская область")]
    counts_res = MagicMock()
    counts_res.all.return_value = [(mno.id, 4)]
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[count_res, rows_res, names_res, counts_res]
    )

    page = await mno_service.list_by_volunteer(session, vol_id, page=1, page_size=50)

    assert page.total == 1
    assert len(page.items) == 1
    detail = page.items[0]
    assert isinstance(detail, MnoDetail)
    assert detail.id == mno.id
    assert detail.incidents == 4  # живой COUNT, не статичное поле модели
    assert detail.region_name == "Самарская область"
    count_sql = str(session.execute.call_args_list[0].args[0])
    rows_sql = str(session.execute.call_args_list[1].args[0])
    assert "mno.volunteer_id" in count_sql
    assert "mno.volunteer_id" in rows_sql
    assert "ORDER BY mno.created_at DESC" in rows_sql


@pytest.mark.asyncio
async def test_mno_list_by_volunteer_empty_skips_counts():
    """Пустой результат → items=[], COUNT обращений не запрашивается (нет id)."""
    vol_id = uuid4()
    count_res = MagicMock()
    count_res.scalar_one.return_value = 0
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = []
    names_res = MagicMock()
    names_res.all.return_value = []
    session = AsyncMock()
    # Только 3 вызова: count, rows, region_names (_incident_counts коротко замыкает пустой набор).
    session.execute = AsyncMock(side_effect=[count_res, rows_res, names_res])

    page = await mno_service.list_by_volunteer(session, vol_id, page=1, page_size=50)

    assert page.total == 0
    assert page.items == []
    assert session.execute.await_count == 3


def _mock_mno(**kw):
    """MagicMock площадки МНО с полями, которые читает _to_list_item (name — служебный у Mock)."""
    base = dict(
        id=uuid4(),
        reg="",
        region_code="63",
        city="Кинель",
        address="ул. Ленина, 1",
        coords="53.2, 50.6",
        source="volunteer",
        fgis_id=None,
        synced=False,
        sync_date=None,
        incidents=0,
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        comment=None,
        photo_urls=[],
        volunteer_id=None,
    )
    base.update(kw)
    m = MagicMock(**base)
    m.name = kw.get("name", "Площадка A")
    return m


def test_to_list_item_populates_volunteer_fields():
    """Волонтёрское МНО: comment/photo_urls из модели + логин/контакт из карты волонтёров."""
    vid = uuid4()
    m = _mock_mno(
        volunteer_id=vid,
        comment="Свалка у забора",
        photo_urls=["/api/v1/intake/mno-photo/x/0.jpg", "/api/v1/intake/mno-photo/x/1.jpg"],
    )
    vol = MagicMock(email="volunteer@list.ru", phone="+79990000000")
    item = _to_list_item(m, {"63": "Самарская область"}, 3, {vid: vol})
    assert item.region_name == "Самарская область"
    assert item.incidents == 3  # живой COUNT перекрывает статичное поле
    assert item.received_at == m.created_at
    assert item.comment == "Свалка у забора"
    assert item.photo_urls == [
        "/api/v1/intake/mno-photo/x/0.jpg",
        "/api/v1/intake/mno-photo/x/1.jpg",
    ]
    assert item.volunteer_login == "volunteer@list.ru"
    assert item.volunteer_contact == "+79990000000"


def test_to_list_item_fgis_leaves_volunteer_fields_empty():
    """ФГИС/ручное МНО (volunteer_id=None, нет карты): волонтёрские поля пусты."""
    m = _mock_mno(source="fgis", reg="63-04-001162", volunteer_id=None, comment=None, photo_urls=[])
    item = _to_list_item(m, {"63": "Самарская область"}, 0, None)
    assert item.volunteer_login is None
    assert item.volunteer_contact is None
    assert item.comment is None
    assert item.photo_urls == []


def test_sort_columns_has_received_created_at():
    """Ключ сортировки 'received' → Mno.created_at (дефолт «Новых МНО», свежие первыми)."""
    from app.services.mno import _SORT_COLUMNS

    assert _SORT_COLUMNS["received"] is Mno.created_at
