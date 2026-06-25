"""Тесты /incidents — офлайн, сервисный слой замокан."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.schemas.base import Paginated
from app.schemas.incident import FunnelCounts, IncidentDetail, IncidentListItem


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
        photo_time=datetime(2026, 4, 26, 8, 5, tzinfo=timezone.utc),
        photos=1,
        photo_urls=["placeholder://incident-photo/1"],
        msg="max-msg-1",
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
