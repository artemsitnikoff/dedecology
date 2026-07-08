"""Тесты /incidents — офлайн, сервисный слой замокан."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.sql.operators import eq

from app.core.errors import NotFoundError
from app.schemas.base import Paginated
from app.schemas.incident import (
    FunnelCounts,
    IncidentDetail,
    IncidentListItem,
    IncidentPoint,
    IncidentPointsResponse,
)
from app.services import incident as incident_service
from app.services.incident import _base_filters, _short_address


def _list_item(**kw):
    base = dict(
        id=uuid4(),
        source="max",
        status="new",
        fio="Громов Сергей Петрович",
        region="Самарская область",
        city="г. Кинель",
        street="ул. Маяковского, 41",
        coords="53.2229, 50.6291",
        photo_time=datetime(2026, 4, 26, 8, 5, tzinfo=timezone.utc),
        photos=1,
        photo_urls=["placeholder://incident-photo/1"],
        msg="max-msg-1",
        msg_url="https://max.ru/c/-75787158905457/AZ8DNeZnbkM",
        received_at=datetime(2026, 4, 26, 8, 11, tzinfo=timezone.utc),
    )
    base.update(kw)
    return IncidentListItem(**base)


def _detail(**kw):
    base = dict(
        id=uuid4(),
        source="max",
        status="found",
        fio="Громов Сергей Петрович",
        region="Самарская область",
        city="г. Кинель",
        street="ул. Маяковского, 41",
        coords="53.2229, 50.6291",
        comment="Радар №116434; Баки раздельного сбора отсутствуют",
        photo_time=datetime(2026, 4, 26, 8, 5, tzinfo=timezone.utc),
        photos=1,
        photo_urls=["placeholder://incident-photo/1"],
        msg="max-msg-1",
        msg_url="https://max.ru/c/-75787158905457/AZ8DNeZnbkM",
        bins=None,
        received_at=datetime(2026, 4, 26, 8, 11, tzinfo=timezone.utc),
        created_at=datetime(2026, 4, 26, 8, 11, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 26, 8, 11, tzinfo=timezone.utc),
    )
    base.update(kw)
    return IncidentDetail(**base)


@pytest.mark.asyncio
async def test_list_incidents_returns_paginated(client):
    page = Paginated[IncidentListItem](
        items=[_list_item()], total=1, page=1, page_size=100, pages=1
    )
    with patch(
        "app.api.v1.incidents.incident_service.list_incidents",
        new=AsyncMock(return_value=page),
    ):
        resp = await client.get("/api/v1/incidents?search=Громов&source=max&status=new")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["fio"] == "Громов Сергей Петрович"
    # Готовый https-URL сообщения отдаётся в строке списка (как есть).
    assert (
        body["items"][0]["msg_url"]
        == "https://max.ru/c/-75787158905457/AZ8DNeZnbkM"
    )


@pytest.mark.asyncio
async def test_funnel_counts(client):
    counts = FunnelCounts(all=13, new=4, found=4, none=2, exported=3)
    with patch(
        "app.api.v1.incidents.incident_service.funnel_counts",
        new=AsyncMock(return_value=counts),
    ):
        resp = await client.get("/api/v1/incidents/funnel?source=max")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"all": 13, "new": 4, "found": 4, "none": 2, "exported": 3}


@pytest.mark.asyncio
async def test_export_get_returns_xlsx(client):
    with patch(
        "app.api.v1.incidents.incident_service.list_for_export",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.api.v1.incidents.build_xlsx", return_value=b"PK\x03\x04xlsxbytes"
    ):
        resp = await client.get("/api/v1/incidents/export")
    assert resp.status_code == 200
    assert resp.content == b"PK\x03\x04xlsxbytes"
    assert (
        resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    cd = resp.headers["content-disposition"]
    assert "filename*=UTF-8''" in cd
    # Кириллица percent-encoded
    assert "%D0%98%D0%BD%D1%86%D0%B8%D0%B4%D0%B5%D0%BD%D1%82%D1%8B" in cd


@pytest.mark.asyncio
async def test_export_post_selected(client):
    ids = [str(uuid4()), str(uuid4())]
    with patch(
        "app.api.v1.incidents.incident_service.list_by_ids",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.api.v1.incidents.build_xlsx", return_value=b"xlsx-selected"
    ):
        resp = await client.post("/api/v1/incidents/export", json={"ids": ids})
    assert resp.status_code == 200
    assert resp.content == b"xlsx-selected"
    assert "%D0%B2%D1%8B%D0%B1%D1%80%D0%B0%D0%BD%D0%BD%D1%8B%D0%B5" in resp.headers[
        "content-disposition"
    ]


@pytest.mark.asyncio
async def test_get_incident_by_id(client):
    detail = _detail()
    with patch(
        "app.api.v1.incidents.incident_service.get_incident",
        new=AsyncMock(return_value=detail),
    ):
        resp = await client.get(f"/api/v1/incidents/{detail.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(detail.id)
    assert body["bins"] is None
    assert body["msg_url"] == "https://max.ru/c/-75787158905457/AZ8DNeZnbkM"
    assert body["comment"] == "Радар №116434; Баки раздельного сбора отсутствуют"


@pytest.mark.asyncio
async def test_patch_status(client):
    detail = _detail(status="exported")
    with patch(
        "app.api.v1.incidents.incident_service.set_status",
        new=AsyncMock(return_value=detail),
    ):
        resp = await client.patch(
            f"/api/v1/incidents/{detail.id}/status", json={"status": "exported"}
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "exported"


@pytest.mark.asyncio
async def test_patch_status_invalid_value_422(client):
    resp = await client.patch(
        f"/api/v1/incidents/{uuid4()}/status", json={"status": "bogus"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_status(client):
    ids = [str(uuid4()), str(uuid4())]
    with patch(
        "app.api.v1.incidents.incident_service.bulk_status",
        new=AsyncMock(return_value=2),
    ):
        resp = await client.post(
            "/api/v1/incidents/bulk-status",
            json={"ids": ids, "status": "exported"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"updated": 2}


@pytest.mark.asyncio
async def test_bulk_delete(client):
    """Удаление 2 реальных инцидентов → {"deleted": 2}; затем GET /{id} → 404."""
    ids = [uuid4(), uuid4()]

    # Сервис «удаляет» обе реальные строки.
    fake_delete = AsyncMock(return_value=len(ids))
    with patch(
        "app.api.v1.incidents.incident_service.bulk_delete",
        new=fake_delete,
    ):
        resp = await client.post(
            "/api/v1/incidents/bulk-delete",
            json={"ids": [str(i) for i in ids]},
        )
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 2}
    # Роутер передал именно эти id в сервис.
    called_ids = fake_delete.call_args.args[1]
    assert [str(i) for i in called_ids] == [str(i) for i in ids]

    # Удалённые инциденты больше не находятся: GET /{id} → 404.
    with patch(
        "app.api.v1.incidents.incident_service.get_incident",
        new=AsyncMock(side_effect=NotFoundError("Инцидент")),
    ):
        gone = await client.get(f"/api/v1/incidents/{ids[0]}")
    assert gone.status_code == 404


# --- #18 многословный поиск (токенизация, AND по токенам) ----------------------


def test_search_clause_single_token_backward_compatible():
    """Один токен → одна OR-группа ilike (прежнее поведение)."""
    from app.services.incident import _search_clause

    sql = str(_search_clause("Громов")).lower()
    assert sql.count("like") == 6  # fio/region/city/street/coords/msg
    assert " and " not in sql


def test_search_clause_multiword_builds_and_of_or_groups():
    """«Самарская Кинель» → AND из двух OR-групп (каждый токен по всем полям)."""
    from app.services.incident import _search_clause

    sql = str(_search_clause("Самарская Кинель")).lower()
    assert " and " in sql
    assert sql.count("like") == 12  # 6 полей × 2 токена


def test_search_clause_ignores_commas_and_order():
    """«Самарская область, Кинель» → 3 токена (AND); запятые/порядок не важны."""
    from app.services.incident import _search_clause

    sql = str(_search_clause("Самарская область, Кинель")).lower()
    assert sql.count("like") == 18  # 6 полей × 3 токена


def test_search_clause_blank_returns_none():
    """Только разделители → None (клауза не добавляется в _base_filters)."""
    from app.services.incident import _search_clause

    assert _search_clause("   ") is None
    assert _search_clause(" , ; ") is None


def test_base_filters_multiword_search_single_and_clause():
    """_base_filters(«Самарская Кинель») → одна клауза (AND-обёртка токенов)."""
    filters = _base_filters("Самарская Кинель", None, None, None)
    assert len(filters) == 1
    assert " and " in str(filters[0]).lower()


# --- Фильтр по региону (одиночный, ТОЧНОЕ совпадение) --------------------------


def test_base_filters_region_exact_match_not_ilike():
    """region → равенство Incident.region == значение (НЕ ilike), пред-статусный фильтр."""
    filters = _base_filters(None, None, None, None, region="Самарская область")
    assert len(filters) == 1
    clause = filters[0]
    # Именно равенство, а не ilike/like.
    assert clause.operator is eq
    assert clause.right.value == "Самарская область"
    compiled = str(clause).lower()
    assert "ilike" not in compiled and "like" not in compiled


def test_base_filters_region_blank_no_filter():
    """Пусто/пробелы/None → фильтр региона НЕ добавляется."""
    assert _base_filters(None, None, None, None, region=None) == []
    assert _base_filters(None, None, None, None, region="") == []
    assert _base_filters(None, None, None, None, region="   ") == []


def test_base_filters_region_combines_with_source():
    """region честится вместе с source (оба пред-статусные → оба в where)."""
    filters = _base_filters(None, ["max"], None, None, region="Самарская область")
    assert len(filters) == 2


@pytest.mark.asyncio
async def test_list_forwards_region(client):
    """GET /incidents?region=... пробрасывает region в сервис списка (сужение списка)."""
    page = Paginated[IncidentListItem](
        items=[_list_item()], total=1, page=1, page_size=100, pages=1
    )
    spy = AsyncMock(return_value=page)
    with patch("app.api.v1.incidents.incident_service.list_incidents", new=spy):
        resp = await client.get("/api/v1/incidents?region=Самарская область")
    assert resp.status_code == 200
    assert spy.call_args.kwargs["region"] == "Самарская область"


# --- Фильтр по типу инцидента (одиночный, ТОЧНОЕ совпадение по коду) -----------


def test_base_filters_incident_type_exact_match():
    """incident_type → равенство Incident.incident_type == код (пред-статусный фильтр)."""
    filters = _base_filters(None, None, None, None, incident_type="fire")
    assert len(filters) == 1
    clause = filters[0]
    assert clause.operator is eq
    assert clause.right.value == "fire"


def test_base_filters_incident_type_blank_no_filter():
    """Пусто/пробелы/None → фильтр типа НЕ добавляется."""
    assert _base_filters(None, None, None, None, incident_type=None) == []
    assert _base_filters(None, None, None, None, incident_type="") == []
    assert _base_filters(None, None, None, None, incident_type="   ") == []


def test_base_filters_incident_type_combines_with_region():
    """incident_type честится вместе с region (оба пред-статусные → оба в where)."""
    filters = _base_filters(
        None, None, None, None, region="Самарская область", incident_type="fire"
    )
    assert len(filters) == 2


@pytest.mark.asyncio
async def test_list_forwards_incident_type(client):
    """GET /incidents?incident_type=... пробрасывает код в сервис списка (сужение)."""
    page = Paginated[IncidentListItem](
        items=[_list_item()], total=1, page=1, page_size=100, pages=1
    )
    spy = AsyncMock(return_value=page)
    with patch("app.api.v1.incidents.incident_service.list_incidents", new=spy):
        resp = await client.get("/api/v1/incidents?incident_type=fire")
    assert resp.status_code == 200
    assert spy.call_args.kwargs["incident_type"] == "fire"


# --- Фильтр по МНО (mno_id, ТОЧНОЕ совпадение по ссылке) -----------------------


def test_base_filters_mno_id_valid_uuid():
    """Валидный mno_id → равенство Incident.mno_id == UUID (пред-статусный фильтр)."""
    mid = uuid4()
    filters = _base_filters(None, None, None, None, mno_id=str(mid))
    assert len(filters) == 1
    clause = filters[0]
    assert clause.operator is eq
    assert clause.right.value == mid


def test_base_filters_mno_id_invalid_or_blank_no_filter():
    """Пусто/пробелы/None/не-UUID → фильтр по МНО НЕ добавляется (не роняем запрос)."""
    assert _base_filters(None, None, None, None, mno_id=None) == []
    assert _base_filters(None, None, None, None, mno_id="") == []
    assert _base_filters(None, None, None, None, mno_id="   ") == []
    assert _base_filters(None, None, None, None, mno_id="not-a-uuid") == []


def test_base_filters_mno_id_combines_with_region():
    """mno_id честится вместе с region (оба пред-статусные → оба в where)."""
    filters = _base_filters(
        None, None, None, None, region="Самарская область", mno_id=str(uuid4())
    )
    assert len(filters) == 2


@pytest.mark.asyncio
async def test_list_forwards_mno_id(client):
    """GET /incidents?mno_id=... пробрасывает id в сервис списка («инциденты этого МНО»)."""
    mid = str(uuid4())
    page = Paginated[IncidentListItem](
        items=[_list_item()], total=1, page=1, page_size=100, pages=1
    )
    spy = AsyncMock(return_value=page)
    with patch("app.api.v1.incidents.incident_service.list_incidents", new=spy):
        resp = await client.get(f"/api/v1/incidents?mno_id={mid}")
    assert resp.status_code == 200
    assert spy.call_args.kwargs["mno_id"] == mid


@pytest.mark.asyncio
async def test_detail_carries_mno_id(client):
    """Карточка инцидента отдаёт mno_id/mno_reg (для ссылки «Объект ТКО» в drawer)."""
    mid = uuid4()
    detail = _detail(mno_id=mid, mno_reg="63-04-001162")
    with patch(
        "app.api.v1.incidents.incident_service.get_incident",
        new=AsyncMock(return_value=detail),
    ):
        resp = await client.get(f"/api/v1/incidents/{detail.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mno_id"] == str(mid)
    assert body["mno_reg"] == "63-04-001162"


@pytest.mark.asyncio
async def test_funnel_forwards_region(client):
    """GET /incidents/funnel?region=... пробрасывает region (влияет на счётчики)."""
    counts = FunnelCounts(all=2, new=1, found=1, none=0, exported=0)
    spy = AsyncMock(return_value=counts)
    with patch("app.api.v1.incidents.incident_service.funnel_counts", new=spy):
        resp = await client.get("/api/v1/incidents/funnel?region=Самарская область")
    assert resp.status_code == 200
    assert resp.json() == {"all": 2, "new": 1, "found": 1, "none": 0, "exported": 0}
    assert spy.call_args.kwargs["region"] == "Самарская область"


@pytest.mark.asyncio
async def test_export_forwards_region(client):
    """GET /incidents/export?region=... пробрасывает region в выборку экспорта."""
    spy = AsyncMock(return_value=[])
    with patch(
        "app.api.v1.incidents.incident_service.list_for_export", new=spy
    ), patch("app.api.v1.incidents.build_xlsx", return_value=b"xlsx"):
        resp = await client.get("/api/v1/incidents/export?region=Самарская область")
    assert resp.status_code == 200
    assert spy.call_args.kwargs["region"] == "Самарская область"


@pytest.mark.asyncio
async def test_regions_endpoint_returns_list(client):
    """GET /incidents/regions → JSON-массив строк (уникальные непустые регионы А→Я)."""
    regions = ["Алтайский край", "Самарская область"]
    with patch(
        "app.api.v1.incidents.incident_service.list_regions",
        new=AsyncMock(return_value=regions),
    ):
        resp = await client.get("/api/v1/incidents/regions")
    assert resp.status_code == 200
    assert resp.json() == regions


@pytest.mark.asyncio
async def test_regions_route_not_shadowed_by_id(client):
    """Литерал /regions объявлен ДО /{id}: его не перехватывает get_incident."""
    spy = AsyncMock(return_value=["Самарская область"])
    with patch(
        "app.api.v1.incidents.incident_service.list_regions", new=spy
    ), patch(
        "app.api.v1.incidents.incident_service.get_incident",
        new=AsyncMock(side_effect=AssertionError("get_incident перехватил /regions")),
    ):
        resp = await client.get("/api/v1/incidents/regions")
    assert resp.status_code == 200
    assert resp.json() == ["Самарская область"]
    spy.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_regions_query_shape():
    """list_regions строит SELECT DISTINCT с фильтром непустых и сортировкой A→Я."""
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        "Алтайский край",
        "Самарская область",
    ]
    session.execute.return_value = result

    regions = await incident_service.list_regions(session)
    assert regions == ["Алтайский край", "Самарская область"]

    stmt = session.execute.call_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True})).upper()
    assert "DISTINCT" in compiled
    assert "ORDER BY" in compiled
    assert "IS NOT NULL" in compiled


# --- /points (карта) -----------------------------------------------------------


@pytest.mark.asyncio
async def test_list_points_returns_points(client):
    """GET /incidents/points отдаёт points/total/capped и пробрасывает фильтры списка."""
    points_resp = IncidentPointsResponse(
        points=[
            IncidentPoint(
                id=uuid4(),
                coords="53.2229, 50.6291",
                status="new",
                address="г. Кинель, ул. Маяковского, 41",
            )
        ],
        total=4200,
        capped=True,
    )
    spy = AsyncMock(return_value=points_resp)
    with patch("app.api.v1.incidents.incident_service.list_points", new=spy):
        resp = await client.get(
            "/api/v1/incidents/points?search=Кинель&source=max&status=new"
            "&region=Самарская область"
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4200
    assert body["capped"] is True
    assert len(body["points"]) == 1
    assert body["points"][0]["coords"] == "53.2229, 50.6291"
    assert body["points"][0]["status"] == "new"
    assert body["points"][0]["address"] == "г. Кинель, ул. Маяковского, 41"
    kw = spy.call_args.kwargs
    assert kw["search"] == "Кинель"
    assert kw["source"] == ["max"]
    assert kw["status"] == ["new"]
    assert kw["region"] == "Самарская область"


@pytest.mark.asyncio
async def test_points_route_not_shadowed_by_id(client):
    """Литерал /points объявлен ДО /{id}: его не перехватывает get_incident."""
    with patch(
        "app.api.v1.incidents.incident_service.list_points",
        new=AsyncMock(
            return_value=IncidentPointsResponse(points=[], total=0, capped=False)
        ),
    ), patch(
        "app.api.v1.incidents.incident_service.get_incident",
        new=AsyncMock(side_effect=AssertionError("get_incident перехватил /points")),
    ):
        resp = await client.get("/api/v1/incidents/points")
    assert resp.status_code == 200
    assert resp.json() == {"points": [], "total": 0, "capped": False}


@pytest.mark.asyncio
async def test_list_points_service_marks_capped():
    """list_points: total из COUNT(*), points из строк с координатами, capped при переполнении."""
    count_res = MagicMock()
    count_res.scalar_one.return_value = incident_service.MAX_POINTS + 5
    row = MagicMock(
        id=uuid4(),
        coords="53.2229, 50.6291",
        status="found",
        region="Самарская область",
        city="г. Кинель",
        street="ул. Маяковского, 41",
    )
    points_res = MagicMock()
    points_res.all.return_value = [row]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, points_res])

    resp = await incident_service.list_points(
        session,
        search=None,
        source=None,
        status=None,
        date_from=None,
        date_to=None,
        region=None,
    )

    assert resp.total == incident_service.MAX_POINTS + 5
    assert resp.capped is True
    assert len(resp.points) == 1
    assert resp.points[0].coords == "53.2229, 50.6291"
    assert resp.points[0].status == "found"
    # Адрес — краткая склейка город+улица (регион в подпись не идёт).
    assert resp.points[0].address == "г. Кинель, ул. Маяковского, 41"


@pytest.mark.asyncio
async def test_list_points_applies_bbox_filter():
    """Валидный bbox → числовой lat/lon-фильтр в WHERE (COUNT и выборка точек)."""
    count_res = MagicMock()
    count_res.scalar_one.return_value = 1
    points_res = MagicMock()
    points_res.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, points_res])

    resp = await incident_service.list_points(
        session,
        search=None,
        source=None,
        status=None,
        date_from=None,
        date_to=None,
        region=None,
        bbox="53.0,50.0,54.0,51.0",
    )

    assert resp.total == 1
    count_sql = str(session.execute.call_args_list[0].args[0])
    points_sql = str(session.execute.call_args_list[1].args[0])
    for sql in (count_sql, points_sql):
        assert "incidents.lat IS NOT NULL" in sql
        assert "incidents.lat BETWEEN" in sql
        assert "incidents.lon BETWEEN" in sql
    # bbox-режим не использует прежний фильтр coords != '' (COUNT его не селектит).
    assert "incidents.coords" not in count_sql


@pytest.mark.asyncio
async def test_list_points_bbox_ignored_when_invalid():
    """Битый bbox → игнор: прежнее поведение (coords != '', без lat/lon-фильтра)."""
    count_res = MagicMock()
    count_res.scalar_one.return_value = 0
    points_res = MagicMock()
    points_res.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, points_res])

    await incident_service.list_points(
        session,
        search=None,
        source=None,
        status=None,
        date_from=None,
        date_to=None,
        region=None,
        bbox="не-bbox",
    )

    points_sql = str(session.execute.call_args_list[1].args[0])
    assert "incidents.coords !=" in points_sql
    assert "BETWEEN" not in points_sql


def test_short_address_joins_nonempty_city_street():
    """_short_address склеивает непустые город/улицу; пустые/пробелы отбрасываются."""
    assert _short_address("Самарская область", "г. Кинель", "ул. Мира, 1") == (
        "г. Кинель, ул. Мира, 1"
    )
    assert _short_address("Самарская область", "", "ул. Мира, 1") == "ул. Мира, 1"
    assert _short_address("Самарская область", "   ", "  ") == ""


@pytest.mark.asyncio
async def test_bulk_delete_skips_nonexistent(client):
    """Несуществующий UUID в запросе не учитывается: deleted = число реальных строк."""
    real_ids = [uuid4(), uuid4()]
    missing_id = uuid4()

    # Сервис no-op-safe: считает только реально удалённые (real_ids), missing пропущен.
    fake_delete = AsyncMock(return_value=len(real_ids))
    with patch(
        "app.api.v1.incidents.incident_service.bulk_delete",
        new=fake_delete,
    ):
        resp = await client.post(
            "/api/v1/incidents/bulk-delete",
            json={"ids": [str(i) for i in (*real_ids, missing_id)]},
        )
    assert resp.status_code == 200
    # deleted отражает только реальные строки, несуществующий id не посчитан.
    assert resp.json() == {"deleted": 2}


# =========================================================================
# list_by_volunteer — «Мои отчёты» (фильтр по volunteer_id, свежие первыми)
# =========================================================================


@pytest.mark.asyncio
async def test_list_by_volunteer_filters_and_orders():
    """list_by_volunteer: WHERE incidents.volunteer_id = :id + ORDER BY created_at DESC;
    COUNT и выборка идут по этому же фильтру."""
    vol_id = uuid4()
    count_res = MagicMock()
    count_res.scalar_one.return_value = 0
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, rows_res])

    page = await incident_service.list_by_volunteer(session, vol_id, page=1, page_size=50)

    assert page.total == 0
    assert page.items == []
    assert page.page == 1 and page.page_size == 50 and page.pages == 0
    count_sql = str(session.execute.call_args_list[0].args[0])
    rows_sql = str(session.execute.call_args_list[1].args[0])
    assert "incidents.volunteer_id" in count_sql
    assert "incidents.volunteer_id" in rows_sql
    assert "ORDER BY incidents.created_at DESC" in rows_sql


@pytest.mark.asyncio
async def test_list_by_volunteer_builds_items_and_pages():
    """Непустой результат → items через IncidentListItem.model_validate, pages округляется вверх."""
    vol_id = uuid4()
    row = _list_item()  # IncidentListItem — совместим с model_validate (from_attributes)
    count_res = MagicMock()
    count_res.scalar_one.return_value = 3
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = [row]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, rows_res])

    page = await incident_service.list_by_volunteer(session, vol_id, page=1, page_size=2)

    assert page.total == 3
    assert page.pages == 2  # ceil(3/2)
    assert len(page.items) == 1
    assert page.items[0].id == row.id
