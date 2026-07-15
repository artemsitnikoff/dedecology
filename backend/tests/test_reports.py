"""Тесты отчётов — офлайн: эндпоинты с замоканным сервисом + юнит-тесты сервиса.

Файлы отчётов в юнит-тестах пишутся в ВРЕМЕННЫЙ каталог (monkeypatch STORAGE_DIR на
tmp_path) — реального STORAGE_DIR не трогаем, сеть/БД не бьём.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.errors import NotFoundError
from app.models import Report
from app.schemas.base import Paginated
from app.schemas.report import ReportCreateRequest, ReportListItem
from app.services import report as report_service


def _report_obj(**kw) -> SimpleNamespace:
    """Объект-снимок отчёта (from_attributes → ReportListItem)."""
    base = dict(
        id=uuid4(),
        kind="incidents",
        filename="Обращения_ЭкоПульс_2026-07-09_10-00.xlsx",
        row_count=3,
        size_bytes=1024,
        created_by_fio="Дед Эколог",
        created_at=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
    )
    base.update(kw)
    return SimpleNamespace(**base)


# --- Эндпоинты (сервис замокан) ------------------------------------------------


@pytest.mark.asyncio
async def test_create_report_endpoint_returns_item(client):
    """POST /reports/incidents → 201 + строка отчёта (ReportListItem)."""
    obj = _report_obj(row_count=5, size_bytes=2048)
    spy = AsyncMock(return_value=obj)
    with patch("app.api.v1.reports.report_service.create_incidents_report", new=spy):
        resp = await client.post("/api/v1/reports/incidents", json={})
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "incidents"
    assert body["row_count"] == 5
    assert body["size_bytes"] == 2048
    assert body["created_by_fio"] == "Дед Эколог"
    # req передан в сервис как ReportCreateRequest.
    assert isinstance(spy.call_args.kwargs["req"], ReportCreateRequest)


@pytest.mark.asyncio
async def test_create_report_endpoint_forwards_filters(client):
    """Фильтры/ids доходят до сервиса в ReportCreateRequest."""
    spy = AsyncMock(return_value=_report_obj())
    with patch("app.api.v1.reports.report_service.create_incidents_report", new=spy):
        resp = await client.post(
            "/api/v1/reports/incidents",
            json={"ids": [str(uuid4())], "region": "63", "status": ["new"]},
        )
    assert resp.status_code == 201
    req = spy.call_args.kwargs["req"]
    assert req.region == "63"
    assert req.status == ["new"]
    assert len(req.ids) == 1


@pytest.mark.asyncio
async def test_list_reports_endpoint_newest_first(client):
    """GET /reports → Paginated[ReportListItem]; порядок сервиса сохраняется."""
    newer = ReportListItem.model_validate(
        _report_obj(created_at=datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc))
    )
    older = ReportListItem.model_validate(
        _report_obj(created_at=datetime(2026, 7, 9, 8, 0, tzinfo=timezone.utc))
    )
    page = Paginated[ReportListItem](
        items=[newer, older], total=2, page=1, page_size=50, pages=1
    )
    with patch(
        "app.api.v1.reports.report_service.list_reports",
        new=AsyncMock(return_value=page),
    ):
        resp = await client.get("/api/v1/reports?page=1&page_size=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["page_size"] == 50
    assert len(body["items"]) == 2
    # Новейший — первым.
    assert body["items"][0]["created_at"] > body["items"][1]["created_at"]


@pytest.mark.asyncio
async def test_download_endpoint_returns_xlsx(client, tmp_path):
    """GET /reports/{id}/download отдаёт реально сохранённый файл (xlsx + attachment)."""
    real = tmp_path / "file.xlsx"
    real.write_bytes(b"PK\x03\x04realreport")
    with patch(
        "app.api.v1.reports.report_service.get_for_download",
        new=AsyncMock(return_value=(real, "Отчёт.xlsx")),
    ):
        resp = await client.get(f"/api/v1/reports/{uuid4()}/download")
    assert resp.status_code == 200
    assert resp.content == b"PK\x03\x04realreport"
    assert (
        resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "filename*=UTF-8''" in resp.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_endpoint_404_when_missing(client):
    """Нет строки/файла → 404 (честный NotFoundError)."""
    with patch(
        "app.api.v1.reports.report_service.get_for_download",
        new=AsyncMock(side_effect=NotFoundError("Отчёт")),
    ):
        resp = await client.get(f"/api/v1/reports/{uuid4()}/download")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_endpoint_returns_message(client):
    """DELETE /reports/{id} → 200 + сообщение."""
    spy = AsyncMock(return_value=None)
    with patch("app.api.v1.reports.report_service.delete_report", new=spy):
        resp = await client.delete(f"/api/v1/reports/{uuid4()}")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Отчёт удалён"
    spy.assert_awaited_once()


@pytest.mark.asyncio
async def test_static_incidents_not_shadowed_by_id(client):
    """POST /reports/incidents (литерал) не перехватывается параметрическим /{id}."""
    spy = AsyncMock(return_value=_report_obj())
    with patch("app.api.v1.reports.report_service.create_incidents_report", new=spy):
        resp = await client.post("/api/v1/reports/incidents", json={})
    assert resp.status_code == 201
    spy.assert_awaited_once()


# --- Сервис (реальная логика, tmp STORAGE_DIR) ---------------------------------


def _session_for_create():
    """Fake AsyncSession: add копит объекты, flush присваивает Report.id."""
    added: list = []
    session = AsyncMock()
    session.add = MagicMock(side_effect=added.append)

    async def _flush():
        for o in added:
            if isinstance(o, Report) and o.id is None:
                o.id = uuid4()

    session.flush = AsyncMock(side_effect=_flush)
    return session, added


def _user():
    return SimpleNamespace(id=uuid4(), fio="Иван Инспектор")


@pytest.mark.asyncio
async def test_create_by_filters_writes_file_and_row(tmp_path, monkeypatch):
    """create по фильтрам: list_for_export, файл на диске, row_count/size_bytes/fio."""
    monkeypatch.setattr(report_service.settings, "STORAGE_DIR", str(tmp_path))
    session, added = _session_for_create()
    user = _user()
    req = ReportCreateRequest(region="63", status=["new"])
    # Строки со статусами — проверяем авто-перевод в «Выгружен» при формировании отчёта.
    fake_rows = [
        SimpleNamespace(status="new"),
        SimpleNamespace(status="found"),
        SimpleNamespace(status="exported"),  # уже выгружен — не считаем повторно
    ]

    with patch(
        "app.services.report.incident_type_service.labels_map",
        new=AsyncMock(return_value={}),
    ), patch(
        # Индекс справочника регионов (канон «Субъект РФ» для инцидентов без МНО) —
        # ходит в БД, которой в тестах нет; поведение резолва проверяет test_utko_export.
        "app.services.report.region_service.canonical_index",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.services.report.incident_service.list_for_export",
        new=AsyncMock(return_value=fake_rows),
    ) as m_export, patch(
        "app.services.report.incident_service.list_by_ids",
        new=AsyncMock(side_effect=AssertionError("не должен вызываться по фильтру")),
    ), patch(
        "app.services.report.build_utko_xlsx", return_value=b"xlsxbytes"
    ), patch(
        "app.services.report.audit", new=AsyncMock()
    ):
        report = await report_service.create_incidents_report(
            session, user, base_url="https://ecopulse.reo.ru", req=req
        )

    m_export.assert_awaited_once()
    # Строка отчёта создана и добавлена в сессию.
    assert isinstance(report, Report)
    assert report in added
    assert report.row_count == 3
    assert report.size_bytes == len(b"xlsxbytes")
    assert report.created_by_fio == "Иван Инспектор"
    assert report.created_by_id == user.id
    assert report.kind == "incidents"
    assert report.filename.endswith(".xlsx")
    assert "_выбранные" not in report.filename
    # Файл реально записан на диск по пути {STORAGE_DIR}/reports/{id}.xlsx.
    path = tmp_path / "reports" / f"{report.id}.xlsx"
    assert path.exists()
    assert path.read_bytes() == b"xlsxbytes"
    # Все включённые обращения переведены в «Выгружен» (в т.ч. уже выгруженное осталось им).
    assert all(r.status == "exported" for r in fake_rows)


@pytest.mark.asyncio
async def test_create_by_filters_forwards_city(tmp_path, monkeypatch):
    """Фильтр по городу доходит из запроса отчёта до выборки (не выкинут молча)."""
    monkeypatch.setattr(report_service.settings, "STORAGE_DIR", str(tmp_path))
    session, _ = _session_for_create()
    req = ReportCreateRequest(region="Самарская область", city="г. Кинель")

    with patch(
        "app.services.report.incident_type_service.labels_map",
        new=AsyncMock(return_value={}),
    ), patch(
        # Индекс справочника регионов (канон «Субъект РФ» для инцидентов без МНО) —
        # ходит в БД, которой в тестах нет; поведение резолва проверяет test_utko_export.
        "app.services.report.region_service.canonical_index",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.services.report.incident_service.list_for_export",
        new=AsyncMock(return_value=[]),
    ) as m_export, patch(
        "app.services.report.build_utko_xlsx", return_value=b"xlsx"
    ), patch(
        "app.services.report.audit", new=AsyncMock()
    ):
        await report_service.create_incidents_report(
            session, _user(), base_url="", req=req
        )

    kw = m_export.await_args.kwargs
    assert kw["city"] == "г. Кинель"
    assert kw["region"] == "Самарская область"


@pytest.mark.asyncio
async def test_create_forwards_region_maps_to_builder(tmp_path, monkeypatch):
    """Обе карты справочника регионов доходят до build_utko_xlsx (не теряются по пути).

    region_by_mno — для инцидентов с МНО, region_index — канон «Субъект РФ» по имени для
    инцидентов БЕЗ МНО. Без индекса в файл уходил бы сырой DaData-текст.
    """
    monkeypatch.setattr(report_service.settings, "STORAGE_DIR", str(tmp_path))
    session, _ = _session_for_create()
    mno_id = uuid4()
    index = {"санкт-петербург": "г. Санкт-Петербург"}
    by_mno = {mno_id: "Самарская область"}

    with patch(
        "app.services.report.incident_type_service.labels_map",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.services.report.region_service.canonical_index",
        new=AsyncMock(return_value=index),
    ), patch(
        "app.services.report.mno_service.region_names_by_mno",
        new=AsyncMock(return_value=by_mno),
    ), patch(
        "app.services.report.incident_service.list_for_export",
        new=AsyncMock(return_value=[SimpleNamespace(status="new", mno_id=mno_id)]),
    ), patch(
        "app.services.report.build_utko_xlsx", return_value=b"xlsx"
    ) as m_build, patch(
        "app.services.report.audit", new=AsyncMock()
    ):
        await report_service.create_incidents_report(
            session, _user(), base_url="", req=ReportCreateRequest()
        )

    args = m_build.call_args.args
    assert by_mno in args  # {mno_id: Region.name}
    assert index in args  # {ключ сопоставления: Region.name}


@pytest.mark.asyncio
async def test_create_by_ids_uses_list_by_ids_and_suffix(tmp_path, monkeypatch):
    """create по ids: list_by_ids + суффикс _выбранные в имени файла."""
    monkeypatch.setattr(report_service.settings, "STORAGE_DIR", str(tmp_path))
    session, added = _session_for_create()
    req = ReportCreateRequest(ids=[str(uuid4()), str(uuid4())])

    ids_row = SimpleNamespace(status="new")
    with patch(
        "app.services.report.incident_type_service.labels_map",
        new=AsyncMock(return_value={}),
    ), patch(
        # Индекс справочника регионов (канон «Субъект РФ» для инцидентов без МНО) —
        # ходит в БД, которой в тестах нет; поведение резолва проверяет test_utko_export.
        "app.services.report.region_service.canonical_index",
        new=AsyncMock(return_value={}),
    ), patch(
        "app.services.report.incident_service.list_by_ids",
        new=AsyncMock(return_value=[ids_row]),
    ) as m_ids, patch(
        "app.services.report.incident_service.list_for_export",
        new=AsyncMock(side_effect=AssertionError("не должен вызываться по ids")),
    ), patch(
        "app.services.report.build_utko_xlsx", return_value=b"xlsx"
    ), patch(
        "app.services.report.audit", new=AsyncMock()
    ):
        report = await report_service.create_incidents_report(
            session, _user(), base_url="", req=req
        )

    m_ids.assert_awaited_once()
    # ids в запросе — UUID (не str): иначе list_by_ids матчит по UUID-ключам впустую → 0 строк.
    assert all(isinstance(i, UUID) for i in req.ids)
    assert report.filename.endswith("_выбранные.xlsx")
    assert report.row_count == 1
    assert ids_row.status == "exported"  # выбранное обращение переведено в «Выгружен»
    assert (tmp_path / "reports" / f"{report.id}.xlsx").exists()


@pytest.mark.asyncio
async def test_get_for_download_returns_path_and_filename(tmp_path, monkeypatch):
    """Строка есть + файл на диске → (path, filename)."""
    monkeypatch.setattr(report_service.settings, "STORAGE_DIR", str(tmp_path))
    rid = uuid4()
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports" / f"{rid}.xlsx").write_bytes(b"data")
    session = AsyncMock()
    session.get = AsyncMock(return_value=SimpleNamespace(filename="Отчёт.xlsx"))

    path, filename = await report_service.get_for_download(session, rid)

    assert path == tmp_path / "reports" / f"{rid}.xlsx"
    assert filename == "Отчёт.xlsx"


@pytest.mark.asyncio
async def test_get_for_download_missing_row_raises(tmp_path, monkeypatch):
    """Нет строки (session.get→None) → NotFoundError."""
    monkeypatch.setattr(report_service.settings, "STORAGE_DIR", str(tmp_path))
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError):
        await report_service.get_for_download(session, uuid4())


@pytest.mark.asyncio
async def test_get_for_download_missing_file_raises(tmp_path, monkeypatch):
    """Строка есть, а файла на диске нет → NotFoundError."""
    monkeypatch.setattr(report_service.settings, "STORAGE_DIR", str(tmp_path))
    session = AsyncMock()
    session.get = AsyncMock(return_value=SimpleNamespace(filename="Отчёт.xlsx"))
    with pytest.raises(NotFoundError):
        await report_service.get_for_download(session, uuid4())


@pytest.mark.asyncio
async def test_delete_report_removes_row_and_file(tmp_path, monkeypatch):
    """Строка есть → session.delete вызван + файл на диске удалён."""
    monkeypatch.setattr(report_service.settings, "STORAGE_DIR", str(tmp_path))
    rid = uuid4()
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    fpath = tmp_path / "reports" / f"{rid}.xlsx"
    fpath.write_bytes(b"data")
    report = SimpleNamespace(filename="Отчёт.xlsx")
    session = AsyncMock()
    session.get = AsyncMock(return_value=report)
    session.delete = AsyncMock()

    with patch("app.services.report.audit", new=AsyncMock()) as m_audit:
        await report_service.delete_report(session, rid, _user())

    session.delete.assert_awaited_once_with(report)
    assert not fpath.exists()
    m_audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_report_missing_row_raises(tmp_path, monkeypatch):
    """Нет строки → NotFoundError (session.delete не вызывается)."""
    monkeypatch.setattr(report_service.settings, "STORAGE_DIR", str(tmp_path))
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.delete = AsyncMock()
    with pytest.raises(NotFoundError):
        await report_service.delete_report(session, uuid4(), _user())
    session.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_reports_builds_paginated(tmp_path, monkeypatch):
    """list_reports: COUNT + строки → Paginated[ReportListItem], pages посчитаны."""
    r1 = Report(
        kind="incidents", filename="a.xlsx", row_count=1, size_bytes=10,
        created_by_id=uuid4(), created_by_fio="A",
    )
    r1.id = uuid4()
    r1.created_at = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)
    count_res = MagicMock()
    count_res.scalar_one.return_value = 1
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = [r1]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, rows_res])

    page = await report_service.list_reports(session, page=1, page_size=50)

    assert page.total == 1
    assert page.pages == 1
    assert len(page.items) == 1
    assert isinstance(page.items[0], ReportListItem)
    assert page.items[0].filename == "a.xlsx"
