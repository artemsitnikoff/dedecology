"""Тесты журнала технических ошибок мобильного приложения — офлайн.

Приём (POST /intake/error-report, защита X-Intake-Token) + админ-просмотр (GET /errors)
с замоканным сервисом; юнит-тесты сервиса (генерация кода, honest emailed/email_error).
БД/сеть не бьём — сессия AsyncMock, smtp.send_email мокается.
"""

import re
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.models import ErrorReport
from app.schemas.base import Paginated
from app.schemas.error_report import ErrorReportCreate, ErrorReportDetail, ErrorReportItem
from app.services import error_report as error_report_service


_CODE_RE = re.compile(r"^ERR-[0-9A-F]{8}$")


def _error_obj(**kw) -> SimpleNamespace:
    base = dict(
        id=uuid4(),
        code="ERR-A1B2C3D4",
        error_type="server",
        message="Серверная ошибка",
        app_version="1.2.3",
        platform="android",
        volunteer_email="v@example.com",
        occurred_at=datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 7, 13, 10, 0, 5, tzinfo=timezone.utc),
        emailed=True,
        user_action="Загрузка фото",
        technical={"stack": "boom"},
        email_error=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _session_for_create():
    """Fake AsyncSession: add копит, flush присваивает ErrorReport.id, code уникален."""
    added: list = []
    session = AsyncMock()
    session.add = MagicMock(side_effect=added.append)

    async def _flush():
        for o in added:
            if isinstance(o, ErrorReport) and o.id is None:
                o.id = uuid4()

    session.flush = AsyncMock(side_effect=_flush)
    # _code_exists → select().scalar_one_or_none() == None (кода ещё нет).
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=res)
    return session, added


# --- Сервис -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_generates_code_and_emails_on_success():
    """Успешная отправка → code формата ERR-XXXXXXXX, emailed=True, email_error пуст."""
    session, added = _session_for_create()
    data = ErrorReportCreate(error_type="server", message="Серверная ошибка")

    with patch(
        "app.services.error_report.smtp_service.send_email", new=AsyncMock()
    ) as m_send:
        error = await error_report_service.create_error_report(session, data)

    assert isinstance(error, ErrorReport)
    assert error in added
    assert _CODE_RE.match(error.code)
    assert error.emailed is True
    assert error.email_error is None
    # Письмо ушло в техподдержку (SUPPORT_EMAIL).
    m_send.assert_awaited_once()
    assert m_send.call_args.kwargs["to"] == settings.SUPPORT_EMAIL
    assert error.code in m_send.call_args.kwargs["subject"]


@pytest.mark.asyncio
async def test_create_registers_even_when_smtp_unconfigured():
    """SMTP не настроен (send_email → ValidationError): строка создана, emailed=False, честный email_error."""
    session, added = _session_for_create()
    data = ErrorReportCreate(error_type="auth")

    with patch(
        "app.services.error_report.smtp_service.send_email",
        new=AsyncMock(side_effect=ValidationError("SMTP не настроен")),
    ):
        error = await error_report_service.create_error_report(session, data)

    # Запрос НЕ упал — ошибка всё равно зарегистрирована.
    assert isinstance(error, ErrorReport)
    assert error in added
    assert error.emailed is False
    assert error.email_error == "SMTP не настроен"


@pytest.mark.asyncio
async def test_create_email_error_on_arbitrary_exception():
    """Любой сбой отправки (не AppError) → emailed=False, email_error=str(exc)."""
    session, _ = _session_for_create()
    data = ErrorReportCreate(error_type="photo_upload")

    with patch(
        "app.services.error_report.smtp_service.send_email",
        new=AsyncMock(side_effect=RuntimeError("connection refused")),
    ):
        error = await error_report_service.create_error_report(session, data)

    assert error.emailed is False
    assert error.email_error == "connection refused"


@pytest.mark.asyncio
async def test_create_technical_defaults_to_empty_dict():
    """technical=None на входе → сохраняется как {} (не NULL)."""
    session, _ = _session_for_create()
    data = ErrorReportCreate(error_type="other", technical=None)

    with patch("app.services.error_report.smtp_service.send_email", new=AsyncMock()):
        error = await error_report_service.create_error_report(session, data)

    assert error.technical == {}


def test_gen_code_format():
    """_gen_code(): ERR- + 8 hex UPPER."""
    for _ in range(20):
        assert _CODE_RE.match(error_report_service._gen_code())


@pytest.mark.asyncio
async def test_list_error_reports_builds_paginated():
    """list: COUNT + строки → Paginated[ErrorReportItem]."""
    r1 = _error_obj()
    count_res = MagicMock()
    count_res.scalar_one.return_value = 1
    rows_res = MagicMock()
    rows_res.scalars.return_value.all.return_value = [r1]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_res, rows_res])

    page = await error_report_service.list_error_reports(session, page=1, page_size=50)

    assert page.total == 1
    assert page.pages == 1
    assert len(page.items) == 1
    assert isinstance(page.items[0], ErrorReportItem)
    assert page.items[0].code == "ERR-A1B2C3D4"


@pytest.mark.asyncio
async def test_get_error_report_missing_raises():
    """Нет строки → NotFoundError."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    with pytest.raises(NotFoundError):
        await error_report_service.get_error_report(session, uuid4())


# --- Эндпоинт приёма (POST /intake/error-report) ------------------------------


@pytest.mark.asyncio
async def test_intake_error_report_requires_token(client, monkeypatch):
    """Без X-Intake-Token → 403, сервис не вызывается."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    spy = AsyncMock(return_value=_error_obj())
    with patch(
        "app.api.v1.intake.error_report_service.create_error_report", new=spy
    ):
        resp = await client.post(
            "/api/v1/intake/error-report", json={"error_type": "server"}
        )
    assert resp.status_code == 403
    spy.assert_not_awaited()


@pytest.mark.asyncio
async def test_intake_error_report_valid_token_201(client, monkeypatch):
    """С верным токеном → 201 + {id, code, created_at, emailed}."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    obj = _error_obj(code="ERR-DEADBEEF", emailed=True)
    spy = AsyncMock(return_value=obj)
    with patch(
        "app.api.v1.intake.error_report_service.create_error_report", new=spy
    ):
        resp = await client.post(
            "/api/v1/intake/error-report",
            json={
                "error_type": "server",
                "message": "Серверная ошибка",
                "app_version": "1.2.3",
                "platform": "android",
                "user_action": "Загрузка фото",
                "technical": {"stack": "boom"},
            },
            headers={"X-Intake-Token": "secret-token"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "ERR-DEADBEEF"
    assert body["emailed"] is True
    assert body["id"] == str(obj.id)
    # payload дошёл сервису как ErrorReportCreate.
    assert isinstance(spy.call_args.args[1], ErrorReportCreate)
    assert spy.call_args.args[1].error_type == "server"


@pytest.mark.asyncio
async def test_intake_error_report_disabled_when_unset(client, monkeypatch):
    """Токен не задан на сервере → 503 INTAKE_DISABLED."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", None)
    resp = await client.post(
        "/api/v1/intake/error-report",
        json={"error_type": "server"},
        headers={"X-Intake-Token": "anything"},
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_intake_error_report_requires_error_type(client, monkeypatch):
    """Пустой error_type → 422 (валидация схемы), сервис не вызывается."""
    monkeypatch.setattr(settings, "YANDEX_INTAKE_TOKEN", "secret-token")
    resp = await client.post(
        "/api/v1/intake/error-report",
        json={"error_type": ""},
        headers={"X-Intake-Token": "secret-token"},
    )
    assert resp.status_code == 422


# --- Админ-просмотр (GET /errors) ---------------------------------------------


@pytest.mark.asyncio
async def test_list_errors_endpoint_returns_paginated(client):
    """GET /errors → Paginated[ErrorReportItem]."""
    item = ErrorReportItem.model_validate(_error_obj())
    page = Paginated[ErrorReportItem](
        items=[item], total=1, page=1, page_size=50, pages=1
    )
    with patch(
        "app.api.v1.errors.error_report_service.list_error_reports",
        new=AsyncMock(return_value=page),
    ):
        resp = await client.get("/api/v1/errors?page=1&page_size=50")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "ERR-A1B2C3D4"


@pytest.mark.asyncio
async def test_get_error_endpoint_returns_detail(client):
    """GET /errors/{id} → ErrorReportDetail (с user_action/technical/email_error)."""
    obj = _error_obj()
    with patch(
        "app.api.v1.errors.error_report_service.get_error_report",
        new=AsyncMock(return_value=obj),
    ):
        resp = await client.get(f"/api/v1/errors/{obj.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "ERR-A1B2C3D4"
    assert body["user_action"] == "Загрузка фото"
    assert body["technical"] == {"stack": "boom"}


@pytest.mark.asyncio
async def test_get_error_endpoint_404(client):
    """GET /errors/{id} нет строки → 404 NOT_FOUND."""
    with patch(
        "app.api.v1.errors.error_report_service.get_error_report",
        new=AsyncMock(side_effect=NotFoundError("Обращение об ошибке")),
    ):
        resp = await client.get(f"/api/v1/errors/{uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_errors_requires_admin(client, current_user):
    """Гейт require_admin: не-админ (role='user') → 403 FORBIDDEN."""
    from app.main import app
    from app.core.permissions import require_admin

    current_user.role = "user"
    app.dependency_overrides.pop(require_admin, None)
    try:
        resp = await client.get("/api/v1/errors")
    finally:
        app.dependency_overrides[require_admin] = lambda: None
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


# --- Миграция 0027 ------------------------------------------------------------


def _load_0027():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "0027_error_reports.py"
    )
    spec = importlib.util.spec_from_file_location("mig_0027", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_0027_revision_identifiers():
    m = _load_0027()
    assert m.revision == "0027"
    assert m.down_revision == "0026"


def test_0027_upgrade_creates_error_reports(monkeypatch):
    """upgrade(): create_table error_reports со всеми колонками + uq на code."""
    m = _load_0027()
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.upgrade()

    fake_op.create_table.assert_called_once()
    args = fake_op.create_table.call_args.args
    assert args[0] == "error_reports"
    col_names = {c.name for c in args[1:] if hasattr(c, "name")}
    assert {
        "id", "code", "error_type", "message", "app_version", "user_action",
        "platform", "technical", "occurred_at", "volunteer_email", "emailed",
        "email_error", "created_at", "updated_at",
    } <= col_names


def test_0027_downgrade_drops_error_reports(monkeypatch):
    """downgrade(): drop_table error_reports."""
    m = _load_0027()
    fake_op = MagicMock()
    monkeypatch.setattr(m, "op", fake_op)

    m.downgrade()

    fake_op.drop_table.assert_called_once_with("error_reports")
