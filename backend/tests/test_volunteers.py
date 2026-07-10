"""Тесты волонтёров — офлайн: сервис/токены реальные, session и внешние вызовы замоканы.

Покрывает: регистрацию (+дубль 409), подтверждение почты (валид/битый токен), логин
(успех / непроверенная почта 403 / блок 403 / неверный пароль 401), сброс пароля
(запрос+смена, токен-флоу), онбординг, изоляцию get_current_volunteer от admin-токена,
админ-справочник (list/active/delete + 403 для не-admin) и отправку писем через UI-SMTP
(SMTP не настроен → ValidationError → email_sent=false → код/токен в ответе).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.errors import (
    AppError,
    BlockedError,
    ConflictError,
    EmailNotVerifiedError,
    ForbiddenError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    ValidationError,
)
from app.core.permissions import require_admin
from app.core.security import (
    create_access_token,
    create_purpose_token,
    create_volunteer_access_token,
    decode_purpose_token,
    get_password_hash,
    verify_password,
)
from app.deps import get_current_user, get_current_volunteer
from app.main import app
from app.models import Volunteer
from app.schemas.volunteer import VolunteerRegister
from app.services import volunteer as vol_service


def _volunteer(
    email_verified=True,
    is_active=True,
    phone=None,
    last_seen_at=None,
    email_code=None,
    email_code_expires_at=None,
    email_code_sent_at=None,
    email_code_attempts=0,
):
    v = Volunteer(
        email="vol@example.com",
        password_hash="x",
        phone=phone,
        email_verified=email_verified,
        is_active=is_active,
    )
    v.id = uuid4()
    v.created_at = datetime.now(timezone.utc)
    v.last_seen_at = last_seen_at
    # OTP-поля подтверждения почты (server_default не применяется к transient-объекту —
    # выставляем явно, чтобы сравнения счётчика попыток не спотыкались о None).
    v.email_code = email_code
    v.email_code_expires_at = email_code_expires_at
    v.email_code_sent_at = email_code_sent_at
    v.email_code_attempts = email_code_attempts
    return v


def _no_existing_session() -> MagicMock:
    """Фейк-сессия: execute().scalar_one_or_none()==None; add синхронный, flush/commit — корутины."""
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


# =========================================================================
# Эндпоинты мобильного контура (без auth)
# =========================================================================


@pytest.mark.asyncio
async def test_register_returns_code_when_email_not_sent(client):
    """SMTP не настроен → email_sent=false и 4-значный код в ответе (честно, без фейка)."""
    vol = _volunteer(email_verified=False)
    # register замокан, но send_email_code — настоящий: он проставит vol.email_code.
    # SMTP не настроен → smtp_service.send_email бросает ValidationError → _try_send=False.
    with patch("app.api.v1.volunteer.register", new=AsyncMock(return_value=vol)), patch(
        "app.services.volunteer.smtp_service.send_email",
        new=AsyncMock(side_effect=ValidationError("SMTP не настроен")),
    ):
        resp = await client.post(
            "/api/v1/volunteer/register",
            json={
                "email": "vol@example.com",
                "password": "secret123",
                "repeat_password": "secret123",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["volunteer_id"] == str(vol.id)
    assert body["email"] == "vol@example.com"
    assert body["email_sent"] is False
    assert body["code_length"] == 4
    assert body["resend_after"] == 60
    # Код присутствует, ровно 4 цифры (SMTP не настроен → отдаём его честно).
    assert body["email_verify_code"] is not None
    assert len(body["email_verify_code"]) == 4
    assert body["email_verify_code"].isdigit()
    assert body["email_verify_code"] == vol.email_code


@pytest.mark.asyncio
async def test_register_password_mismatch_400(client):
    """Пароль ≠ повтор → 400 PASSWORDS_MISMATCH (реальный сервис, до обращения к БД).

    Домен-стоп-лист замокан (не блокирует) — проверяется приоритет ветки паролей.
    """
    with patch(
        "app.services.blocked_domain.is_email_blocked",
        new=AsyncMock(return_value=False),
    ):
        resp = await client.post(
            "/api/v1/volunteer/register",
            json={
                "email": "vol@example.com",
                "password": "secret123",
                "repeat_password": "secret999",
            },
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PASSWORDS_MISMATCH"


@pytest.mark.asyncio
async def test_register_duplicate_email_409(client):
    with patch(
        "app.api.v1.volunteer.register",
        new=AsyncMock(side_effect=ConflictError("Волонтёр с таким email уже зарегистрирован")),
    ):
        resp = await client.post(
            "/api/v1/volunteer/register",
            json={
                "email": "dup@example.com",
                "password": "secret123",
                "repeat_password": "secret123",
            },
        )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_register_short_password_422(client):
    resp = await client.post(
        "/api/v1/volunteer/register",
        json={"email": "x@example.com", "password": "abc", "repeat_password": "abc"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_verify_email_valid(client):
    vol = _volunteer(email_verified=True)
    with patch("app.api.v1.volunteer.verify_email", new=AsyncMock(return_value=vol)):
        resp = await client.post(
            "/api/v1/volunteer/verify-email",
            json={"email": "vol@example.com", "code": "0472"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["email_verified"] is True


@pytest.mark.asyncio
async def test_verify_email_invalid_code_400_passthrough(client):
    """Эндпоинт пробрасывает INVALID_CODE из сервиса с details.attempts_left."""
    with patch(
        "app.api.v1.volunteer.verify_email",
        new=AsyncMock(
            side_effect=AppError(
                "INVALID_CODE", "Неверный код", 400, details={"attempts_left": 3}
            )
        ),
    ):
        resp = await client.post(
            "/api/v1/volunteer/verify-email",
            json={"email": "vol@example.com", "code": "0000"},
        )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "INVALID_CODE"
    assert body["error"]["details"]["attempts_left"] == 3


@pytest.mark.asyncio
async def test_resend_returns_new_code_when_email_not_sent(client):
    """Повторная отправка: письмо не ушло → новый код в ответе (email_sent=false)."""
    vol = _volunteer(email_verified=False, email_code="1234")
    with patch(
        "app.api.v1.volunteer.resend_email_code",
        new=AsyncMock(return_value=(False, False, vol)),
    ):
        resp = await client.post(
            "/api/v1/volunteer/register/resend", json={"email": "vol@example.com"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["email_sent"] is False
    assert body["already_verified"] is False
    assert body["code_length"] == 4
    assert body["resend_after"] == 60
    assert body["email_verify_code"] == "1234"


@pytest.mark.asyncio
async def test_resend_too_soon_429(client):
    """Кулдаун не прошёл → 429 RESEND_TOO_SOON с details.resend_after."""
    with patch(
        "app.api.v1.volunteer.resend_email_code",
        new=AsyncMock(
            side_effect=AppError(
                "RESEND_TOO_SOON",
                "Повторная отправка будет доступна позже",
                429,
                details={"resend_after": 42},
            )
        ),
    ):
        resp = await client.post(
            "/api/v1/volunteer/register/resend", json={"email": "vol@example.com"}
        )
    assert resp.status_code == 429
    body = resp.json()
    assert body["error"]["code"] == "RESEND_TOO_SOON"
    assert body["error"]["details"]["resend_after"] == 42


@pytest.mark.asyncio
async def test_resend_already_verified_no_code(client):
    """Почта уже подтверждена → already_verified=true, код НЕ отдаём."""
    vol = _volunteer(email_verified=True)
    with patch(
        "app.api.v1.volunteer.resend_email_code",
        new=AsyncMock(return_value=(False, True, vol)),
    ):
        resp = await client.post(
            "/api/v1/volunteer/register/resend", json={"email": "vol@example.com"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["already_verified"] is True
    assert body["email_verify_code"] is None


@pytest.mark.asyncio
async def test_login_success(client):
    vol = _volunteer(email_verified=True, is_active=True, phone="+79990001122")
    with patch("app.api.v1.volunteer.authenticate", new=AsyncMock(return_value=vol)), patch(
        "app.api.v1.volunteer.create_volunteer_access_token", return_value="vol-access"
    ):
        resp = await client.post(
            "/api/v1/volunteer/login",
            json={"email": "vol@example.com", "password": "secret123"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] == "vol-access"
    assert body["token_type"] == "bearer"
    assert body["volunteer"]["email"] == "vol@example.com"
    assert body["volunteer"]["phone"] == "+79990001122"
    assert body["volunteer"]["email_verified"] is True


@pytest.mark.asyncio
async def test_login_email_not_verified_403(client):
    with patch(
        "app.api.v1.volunteer.authenticate",
        new=AsyncMock(side_effect=EmailNotVerifiedError()),
    ):
        resp = await client.post(
            "/api/v1/volunteer/login",
            json={"email": "vol@example.com", "password": "secret123"},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


@pytest.mark.asyncio
async def test_login_blocked_403(client):
    with patch(
        "app.api.v1.volunteer.authenticate",
        new=AsyncMock(side_effect=BlockedError()),
    ):
        resp = await client.post(
            "/api/v1/volunteer/login",
            json={"email": "vol@example.com", "password": "secret123"},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "BLOCKED"


@pytest.mark.asyncio
async def test_login_wrong_password_401(client):
    with patch(
        "app.api.v1.volunteer.authenticate",
        new=AsyncMock(side_effect=InvalidCredentialsError()),
    ):
        resp = await client.post(
            "/api/v1/volunteer/login",
            json={"email": "vol@example.com", "password": "wrong"},
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_reset_request_existing_returns_token(client):
    """Волонтёр найден, письмо не ушло (нет SMTP) → reset-токен/ссылка в ответе."""
    vol = _volunteer()
    # request_password_reset замокан, но send_reset_email — настоящий (генерит токен/URL).
    # SMTP не настроен → smtp_service.send_email бросает ValidationError → email_sent=False.
    with patch(
        "app.api.v1.volunteer.request_password_reset", new=AsyncMock(return_value=vol)
    ), patch(
        "app.services.volunteer.smtp_service.send_email",
        new=AsyncMock(side_effect=ValidationError("SMTP не настроен")),
    ):
        resp = await client.post(
            "/api/v1/volunteer/password/reset-request", json={"email": "vol@example.com"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["email_sent"] is False
    assert body["reset_token"]
    assert decode_purpose_token(body["reset_token"], "reset_password") == str(vol.id)


@pytest.mark.asyncio
async def test_reset_request_unknown_email_no_token(client):
    """Неизвестный email → ok=true, БЕЗ токена (анти-энумерация)."""
    with patch(
        "app.api.v1.volunteer.request_password_reset", new=AsyncMock(return_value=None)
    ):
        resp = await client.post(
            "/api/v1/volunteer/password/reset-request", json={"email": "nobody@example.com"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["email_sent"] is False
    assert body["reset_token"] is None
    assert body["reset_url"] is None


@pytest.mark.asyncio
async def test_reset_password_success(client):
    vol = _volunteer()
    with patch("app.api.v1.volunteer.reset_password", new=AsyncMock(return_value=vol)):
        resp = await client.post(
            "/api/v1/volunteer/password/reset",
            json={"token": "good", "new_password": "newsecret"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_reset_password_invalid_token_400(client):
    with patch(
        "app.api.v1.volunteer.reset_password",
        new=AsyncMock(side_effect=InvalidTokenError()),
    ):
        resp = await client.post(
            "/api/v1/volunteer/password/reset",
            json={"token": "broken", "new_password": "newsecret"},
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_reset_password_short_422(client):
    resp = await client.post(
        "/api/v1/volunteer/password/reset",
        json={"token": "good", "new_password": "abc"},
    )
    assert resp.status_code == 422


# =========================================================================
# Мобильный контур с авторизацией волонтёра (get_current_volunteer)
# =========================================================================


@pytest.mark.asyncio
async def test_volunteer_me(client):
    vol = _volunteer(phone="+79995554433")
    app.dependency_overrides[get_current_volunteer] = lambda: vol
    try:
        resp = await client.get("/api/v1/volunteer/me")
    finally:
        app.dependency_overrides.pop(get_current_volunteer, None)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == vol.email
    assert body["phone"] == "+79995554433"


@pytest.mark.asyncio
async def test_volunteer_onboarding_sets_phone(client):
    vol = _volunteer(phone=None)
    updated = _volunteer(phone="+79990000000")
    app.dependency_overrides[get_current_volunteer] = lambda: vol
    try:
        with patch(
            "app.api.v1.volunteer.complete_onboarding", new=AsyncMock(return_value=updated)
        ):
            resp = await client.patch(
                "/api/v1/volunteer/onboarding", json={"phone": "+79990000000"}
            )
    finally:
        app.dependency_overrides.pop(get_current_volunteer, None)
    assert resp.status_code == 200
    assert resp.json()["phone"] == "+79990000000"


@pytest.mark.asyncio
async def test_get_current_volunteer_rejects_admin_token(client):
    """Изоляция: admin access-токен (claim type=access, без typ) НЕ проходит в /volunteer/*."""
    admin_token = create_access_token(data={"sub": str(uuid4())})
    resp = await client.get(
        "/api/v1/volunteer/me", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.asyncio
async def test_get_current_volunteer_rejects_missing_bearer(client):
    resp = await client.get("/api/v1/volunteer/me")
    assert resp.status_code in (401, 403)  # HTTPBearer сам отдаёт 403 при отсутствии заголовка


def _session_returning(volunteer) -> MagicMock:
    """Фейк-сессия, чей execute().scalar_one_or_none() возвращает данного волонтёра."""
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = volunteer
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_current_volunteer_sets_last_seen_when_empty():
    """last_seen_at пуст → обновляется и коммитится (последняя авторизация = этот запрос)."""
    vol = _volunteer(last_seen_at=None)
    session = _session_returning(vol)
    token = create_volunteer_access_token(str(vol.id))

    returned = await get_current_volunteer(
        token=SimpleNamespace(credentials=token), session=session
    )
    assert returned is vol
    assert vol.last_seen_at is not None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_current_volunteer_throttles_last_seen():
    """last_seen_at обновлён недавно (<60с) → повторной записи/commit нет (троттлинг)."""
    recent = datetime.now(timezone.utc)
    vol = _volunteer(last_seen_at=recent)
    session = _session_returning(vol)
    token = create_volunteer_access_token(str(vol.id))

    returned = await get_current_volunteer(
        token=SimpleNamespace(credentials=token), session=session
    )
    assert returned is vol
    assert vol.last_seen_at == recent  # не переписан
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_current_volunteer_updates_stale_last_seen():
    """last_seen_at старше 60с → обновляется и коммитится."""
    stale = datetime.now(timezone.utc) - timedelta(minutes=5)
    vol = _volunteer(last_seen_at=stale)
    session = _session_returning(vol)
    token = create_volunteer_access_token(str(vol.id))

    await get_current_volunteer(token=SimpleNamespace(credentials=token), session=session)
    assert vol.last_seen_at > stale
    session.commit.assert_awaited_once()


# =========================================================================
# Таб «Отчёты»: GET /volunteer/reports и /volunteer/mno (get_current_volunteer)
# =========================================================================


@pytest.mark.asyncio
async def test_my_reports_requires_auth(client):
    """GET /volunteer/reports без токена → требует авторизацию (HTTPBearer 401/403)."""
    resp = await client.get("/api/v1/volunteer/reports")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_my_mno_requires_auth(client):
    """GET /volunteer/mno без токена → требует авторизацию."""
    resp = await client.get("/api/v1/volunteer/mno")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_my_reports_returns_paginated_for_volunteer(client):
    """GET /volunteer/reports (авторизован) → 200 Paginated; сервис зовётся с id волонтёра."""
    from app.schemas.base import Paginated
    from app.schemas.incident import IncidentListItem

    vol = _volunteer()
    app.dependency_overrides[get_current_volunteer] = lambda: vol
    page = Paginated[IncidentListItem](items=[], total=0, page=1, page_size=50, pages=0)
    spy = AsyncMock(return_value=page)
    try:
        with patch(
            "app.api.v1.volunteer.incident_service.list_by_volunteer", new=spy
        ):
            resp = await client.get("/api/v1/volunteer/reports")
    finally:
        app.dependency_overrides.pop(get_current_volunteer, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []
    # Фильтрация именно по id ЭТОГО волонтёра (2-й позиционный аргумент — current_volunteer.id).
    spy.assert_awaited_once()
    assert spy.call_args.args[1] == vol.id


@pytest.mark.asyncio
async def test_my_mno_returns_paginated_for_volunteer(client):
    """GET /volunteer/mno (авторизован) → 200 Paginated[MnoDetail]; сервис зовётся с id волонтёра."""
    from app.schemas.base import Paginated
    from app.schemas.mno import MnoDetail

    vol = _volunteer()
    app.dependency_overrides[get_current_volunteer] = lambda: vol
    page = Paginated[MnoDetail](items=[], total=0, page=1, page_size=50, pages=0)
    spy = AsyncMock(return_value=page)
    try:
        with patch("app.api.v1.volunteer.mno_service.list_by_volunteer", new=spy):
            resp = await client.get("/api/v1/volunteer/mno")
    finally:
        app.dependency_overrides.pop(get_current_volunteer, None)

    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    spy.assert_awaited_once()
    assert spy.call_args.args[1] == vol.id


@pytest.mark.asyncio
async def test_my_reports_clamps_pagination(client):
    """page < 1 → 1, page_size > 200 → 200 (защита от перебора)."""
    from app.schemas.base import Paginated
    from app.schemas.incident import IncidentListItem

    vol = _volunteer()
    app.dependency_overrides[get_current_volunteer] = lambda: vol
    page = Paginated[IncidentListItem](items=[], total=0, page=1, page_size=200, pages=0)
    spy = AsyncMock(return_value=page)
    try:
        with patch(
            "app.api.v1.volunteer.incident_service.list_by_volunteer", new=spy
        ):
            resp = await client.get(
                "/api/v1/volunteer/reports?page=0&page_size=9999"
            )
    finally:
        app.dependency_overrides.pop(get_current_volunteer, None)

    assert resp.status_code == 200
    assert spy.call_args.kwargs["page"] == 1
    assert spy.call_args.kwargs["page_size"] == 200


# =========================================================================
# Админ-справочник /volunteers (require_admin)
# =========================================================================


@pytest.mark.asyncio
async def test_admin_list_volunteers(client):
    vol = _volunteer(phone="+79990001122")
    with patch(
        "app.services.volunteer.list_all", new=AsyncMock(return_value=[vol])
    ), patch(
        "app.api.v1.volunteers.volunteer_service.incidents_counts_map",
        new=AsyncMock(return_value={vol.id: 5}),
    ):
        resp = await client.get("/api/v1/volunteers")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["email"] == "vol@example.com"
    assert body[0]["is_active"] is True
    assert body[0]["email_verified"] is True
    assert "created_at" in body[0]
    # «Последняя авторизация» присутствует в строке справочника (null, вход не совершался).
    assert "last_seen_at" in body[0]
    assert body[0]["last_seen_at"] is None
    assert "fio" not in body[0]  # поле «Заявитель» у волонтёра убрано
    # Кол-во обращений волонтёра — из GROUP BY (incidents_counts_map).
    assert body[0]["incidents_count"] == 5


@pytest.mark.asyncio
async def test_admin_list_volunteers_zero_count_when_no_incidents(client):
    """Волонтёр без обращений (нет в counts-map) → incidents_count=0 (а не отсутствует)."""
    vol = _volunteer()
    with patch(
        "app.services.volunteer.list_all", new=AsyncMock(return_value=[vol])
    ), patch(
        "app.api.v1.volunteers.volunteer_service.incidents_counts_map",
        new=AsyncMock(return_value={}),
    ):
        resp = await client.get("/api/v1/volunteers")
    assert resp.status_code == 200
    assert resp.json()[0]["incidents_count"] == 0


@pytest.mark.asyncio
async def test_incidents_counts_map_groups_by_volunteer():
    """incidents_counts_map: пустой список id → {} без запроса; иначе GROUP BY → {id: count}."""
    session = AsyncMock()
    # Пустой список — БД не трогаем.
    assert await vol_service.incidents_counts_map(session, []) == {}
    session.execute.assert_not_called()

    vid1, vid2 = uuid4(), uuid4()
    result = MagicMock()
    result.all.return_value = [(vid1, 3), (vid2, 1)]
    session.execute = AsyncMock(return_value=result)
    counts = await vol_service.incidents_counts_map(session, [vid1, vid2, None, vid1])
    assert counts == {vid1: 3, vid2: 1}
    # GROUP BY по volunteer_id действительно в запросе.
    sql = str(session.execute.call_args.args[0]).lower()
    assert "group by" in sql
    assert "volunteer_id" in sql


@pytest.mark.asyncio
async def test_admin_set_volunteer_active(client):
    vol = _volunteer(is_active=False)
    with patch("app.services.volunteer.set_active", new=AsyncMock(return_value=vol)):
        resp = await client.patch(
            f"/api/v1/volunteers/{uuid4()}/active", json={"is_active": False}
        )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_admin_delete_volunteer_204(client):
    with patch("app.services.volunteer.delete", new=AsyncMock(return_value=None)):
        resp = await client.delete(f"/api/v1/volunteers/{uuid4()}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_admin_volunteers_forbidden_for_non_admin(client):
    """Не-admin → 403 (гейт require_admin на роутере /volunteers)."""
    async def _deny():
        raise ForbiddenError("Требуется роль администратора")

    app.dependency_overrides[require_admin] = _deny
    try:
        resp = await client.get("/api/v1/volunteers")
    finally:
        # Вернём проходной override из фикстуры client (teardown всё равно очистит).
        app.dependency_overrides[require_admin] = lambda: None
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


# =========================================================================
# Токены — реальная логика
# =========================================================================


def test_purpose_token_roundtrip_and_purpose_isolation():
    vid = str(uuid4())
    tok = create_purpose_token(vid, "verify_email", timedelta(hours=1))
    assert decode_purpose_token(tok, "verify_email") == vid
    # Чужой purpose → None
    assert decode_purpose_token(tok, "reset_password") is None
    # Мусор → None
    assert decode_purpose_token("garbage.token.value", "verify_email") is None


def test_token_claim_shapes_guarantee_isolation():
    """Admin access-токен имеет type=access (без typ); volunteer — typ=volunteer (без type)."""
    from app.core.security import decode_token

    admin_tok = create_access_token(data={"sub": str(uuid4())})
    vol_tok = create_volunteer_access_token(str(uuid4()))

    admin_payload = decode_token(admin_tok)
    vol_payload = decode_token(vol_tok)

    assert admin_payload.get("type") == "access"
    assert admin_payload.get("typ") is None  # → get_current_volunteer отбракует
    assert vol_payload.get("typ") == "volunteer"
    assert vol_payload.get("type") is None  # → get_current_user отбракует


# =========================================================================
# Сервисный слой — реальная логика (session замокан)
# =========================================================================


@pytest.mark.asyncio
async def test_service_register_hashes_password_and_sets_flags():
    session = _no_existing_session()
    data = VolunteerRegister(
        email="vol@example.com", password="secret123", repeat_password="secret123"
    )
    with patch(
        "app.services.blocked_domain.is_email_blocked",
        new=AsyncMock(return_value=False),
    ):
        vol = await vol_service.register(session, data)
    assert vol.email_verified is False
    assert vol.is_active is True
    assert vol.phone is None
    assert verify_password("secret123", vol.password_hash) is True
    assert verify_password("wrong", vol.password_hash) is False


@pytest.mark.asyncio
async def test_service_register_password_mismatch():
    """Пароль ≠ повтор → PASSWORDS_MISMATCH (400), БД не трогается."""
    session = _no_existing_session()
    data = VolunteerRegister(
        email="vol@example.com", password="secret123", repeat_password="secret999"
    )
    with patch(
        "app.services.blocked_domain.is_email_blocked",
        new=AsyncMock(return_value=False),
    ), pytest.raises(AppError) as exc:
        await vol_service.register(session, data)
    assert exc.value.code == "PASSWORDS_MISMATCH"
    assert exc.value.status_code == 400
    # До проверки дубля дело не дошло — email в БД не запрашивали (домен-стоп-лист замокан).
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_service_register_duplicate_conflict():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _volunteer()  # email уже есть
    session.execute = AsyncMock(return_value=result)
    data = VolunteerRegister(
        email="vol@example.com", password="secret123", repeat_password="secret123"
    )
    with patch(
        "app.services.blocked_domain.is_email_blocked",
        new=AsyncMock(return_value=False),
    ), pytest.raises(ConflictError):
        await vol_service.register(session, data)


@pytest.mark.asyncio
async def test_service_authenticate_flow():
    session = AsyncMock()
    verified = _volunteer(email_verified=True, is_active=True)
    verified.password_hash = get_password_hash("secret123")

    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=verified)):
        # успех + проставлена «последняя авторизация»
        assert verified.last_seen_at is None
        assert await vol_service.authenticate(session, "vol@example.com", "secret123") is verified
        assert verified.last_seen_at is not None
        # неверный пароль → 401
        with pytest.raises(InvalidCredentialsError):
            await vol_service.authenticate(session, "vol@example.com", "wrong")

    unverified = _volunteer(email_verified=False, is_active=True)
    unverified.password_hash = get_password_hash("secret123")
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=unverified)):
        with pytest.raises(EmailNotVerifiedError):
            await vol_service.authenticate(session, "vol@example.com", "secret123")

    blocked = _volunteer(email_verified=True, is_active=False)
    blocked.password_hash = get_password_hash("secret123")
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=blocked)):
        with pytest.raises(BlockedError):
            await vol_service.authenticate(session, "vol@example.com", "secret123")

    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=None)):
        with pytest.raises(InvalidCredentialsError):
            await vol_service.authenticate(session, "ghost@example.com", "secret123")


def _future(minutes=15):
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


@pytest.mark.asyncio
async def test_service_verify_email_code_success():
    """Верный код → email_verified=true, код обнуляется (одноразовый)."""
    session = MagicMock()
    session.flush = AsyncMock()
    vol = _volunteer(
        email_verified=False, email_code="0472", email_code_expires_at=_future()
    )
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=vol)):
        result = await vol_service.verify_email(session, vol.email, "0472")
    assert result.email_verified is True
    assert vol.email_code is None
    assert vol.email_code_expires_at is None
    assert vol.email_code_attempts == 0


@pytest.mark.asyncio
async def test_service_verify_email_wrong_code_increments_and_locks():
    """Неверный код → attempts+=1 (commit) + INVALID_CODE с attempts_left; после MAX → 429."""
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    vol = _volunteer(
        email_verified=False,
        email_code="0472",
        email_code_expires_at=_future(),
        email_code_attempts=0,
    )
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=vol)):
        # 4 неверные попытки: счётчик растёт, остаток попыток убывает.
        for expected_left in (4, 3, 2, 1):
            with pytest.raises(AppError) as exc:
                await vol_service.verify_email(session, vol.email, "9999")
            assert exc.value.code == "INVALID_CODE"
            assert exc.value.status_code == 400
            assert exc.value.details["attempts_left"] == expected_left
        # 5-я неверная попытка добивает лимит (attempts=5), остаток 0.
        with pytest.raises(AppError) as exc:
            await vol_service.verify_email(session, vol.email, "9999")
        assert exc.value.code == "INVALID_CODE"
        assert exc.value.details["attempts_left"] == 0
        # Теперь код заблокирован: даже верный код → TOO_MANY_ATTEMPTS (429).
        with pytest.raises(AppError) as exc:
            await vol_service.verify_email(session, vol.email, "0472")
        assert exc.value.code == "TOO_MANY_ATTEMPTS"
        assert exc.value.status_code == 429
    # Инкремент коммитился (антибрутфорс переживает raise).
    assert session.commit.await_count >= 5
    assert vol.email_code_attempts == 5


@pytest.mark.asyncio
async def test_service_verify_email_expired_code():
    """Истёкший код → CODE_EXPIRED (400)."""
    session = MagicMock()
    session.flush = AsyncMock()
    vol = _volunteer(
        email_verified=False,
        email_code="0472",
        email_code_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=vol)):
        with pytest.raises(AppError) as exc:
            await vol_service.verify_email(session, vol.email, "0472")
    assert exc.value.code == "CODE_EXPIRED"
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_service_verify_email_already_verified_idempotent():
    """Почта уже подтверждена → ok идемпотентно, без ошибки (даже с любым кодом)."""
    session = MagicMock()
    session.flush = AsyncMock()
    vol = _volunteer(email_verified=True)
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=vol)):
        result = await vol_service.verify_email(session, vol.email, "0000")
    assert result is vol
    assert result.email_verified is True


@pytest.mark.asyncio
async def test_service_verify_email_unknown_email_code_expired():
    """Неизвестный email → CODE_EXPIRED (анти-энумерация: не отличить от истёкшего кода)."""
    session = MagicMock()
    session.flush = AsyncMock()
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await vol_service.verify_email(session, "ghost@example.com", "0472")
    assert exc.value.code == "CODE_EXPIRED"


@pytest.mark.asyncio
async def test_service_resend_too_soon():
    """Код выслан <кулдауна назад → RESEND_TOO_SOON (429) с положительным resend_after."""
    session = MagicMock()
    session.flush = AsyncMock()
    vol = _volunteer(
        email_verified=False,
        email_code="0472",
        email_code_sent_at=datetime.now(timezone.utc) - timedelta(seconds=10),
    )
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=vol)):
        with pytest.raises(AppError) as exc:
            await vol_service.resend_email_code(session, vol.email)
    assert exc.value.code == "RESEND_TOO_SOON"
    assert exc.value.status_code == 429
    assert 0 < exc.value.details["resend_after"] <= 60


@pytest.mark.asyncio
async def test_service_resend_issues_new_code_after_cooldown():
    """Кулдаун прошёл (sent_at в прошлом) → новый код выдан, sent_at обновлён, attempts=0."""
    session = MagicMock()
    session.flush = AsyncMock()
    old_sent = datetime.now(timezone.utc) - timedelta(minutes=5)
    vol = _volunteer(
        email_verified=False,
        email_code="0472",
        email_code_sent_at=old_sent,
        email_code_attempts=3,
    )
    # SMTP не настроен → send_email бросает ValidationError → _try_send → email_sent=False.
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=vol)), patch(
        "app.services.volunteer.smtp_service.send_email",
        new=AsyncMock(side_effect=ValidationError("SMTP не настроен")),
    ):
        email_sent, already_verified, returned = await vol_service.resend_email_code(
            session, vol.email
        )
    assert email_sent is False  # SMTP не настроен → честный False
    assert already_verified is False
    assert returned is vol
    # Выдан новый код (4 цифры), счётчик попыток сброшен, момент отправки обновлён.
    assert vol.email_code is not None and len(vol.email_code) == 4
    assert vol.email_code_attempts == 0
    assert vol.email_code_sent_at > old_sent


@pytest.mark.asyncio
async def test_service_resend_already_verified():
    """Уже подтверждён → (False, True, vol), нового кода не выдаём."""
    session = MagicMock()
    session.flush = AsyncMock()
    vol = _volunteer(email_verified=True, email_code=None)
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=vol)):
        email_sent, already_verified, returned = await vol_service.resend_email_code(
            session, vol.email
        )
    assert email_sent is False
    assert already_verified is True
    assert returned is vol
    assert vol.email_code is None  # код не выдавался


@pytest.mark.asyncio
async def test_service_resend_unknown_email_anti_enumeration():
    """Неизвестный email → (False, False, None): «успех» без кода (анти-энумерация)."""
    session = MagicMock()
    session.flush = AsyncMock()
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=None)):
        email_sent, already_verified, returned = await vol_service.resend_email_code(
            session, "ghost@example.com"
        )
    assert email_sent is False
    assert already_verified is False
    assert returned is None


@pytest.mark.asyncio
async def test_service_verify_after_resend_succeeds():
    """Интеграция: resend выдаёт код → verify этим кодом подтверждает почту."""
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    vol = _volunteer(email_verified=False, email_code_sent_at=None)
    with patch("app.services.volunteer.get_by_email", new=AsyncMock(return_value=vol)), patch(
        "app.services.volunteer.smtp_service.send_email",
        new=AsyncMock(side_effect=ValidationError("SMTP не настроен")),
    ):
        _, _, _ = await vol_service.resend_email_code(session, vol.email)
        fresh_code = vol.email_code
        assert fresh_code is not None
        result = await vol_service.verify_email(session, vol.email, fresh_code)
    assert result.email_verified is True
    assert vol.email_code is None


@pytest.mark.asyncio
async def test_service_reset_password_token_flow():
    session = MagicMock()
    session.flush = AsyncMock()
    vol = _volunteer()
    vol.password_hash = get_password_hash("old-password")
    good = create_purpose_token(str(vol.id), "reset_password", timedelta(hours=1))
    with patch("app.services.volunteer.get_by_id", new=AsyncMock(return_value=vol)):
        await vol_service.reset_password(session, good, "new-password")
    assert verify_password("new-password", vol.password_hash) is True
    assert verify_password("old-password", vol.password_hash) is False

    # verify_email-токен в reset_password → чужой purpose → InvalidTokenError
    verify_tok = create_purpose_token(str(vol.id), "verify_email", timedelta(hours=1))
    with pytest.raises(InvalidTokenError):
        await vol_service.reset_password(session, verify_tok, "whatever")


# =========================================================================
# Админ-триггер сброса пароля волонтёра ПО ID (/volunteers/{id}/reset-password)
# =========================================================================


@pytest.mark.asyncio
async def test_service_admin_reset_password_returns_token_without_smtp():
    """Успех: SMTP нет → email_sent=false, валидный reset-токен вернулся + email волонтёра.

    Прямой смены пароля НЕТ — password_hash не меняется (только письмо/токен)."""
    vol = _volunteer()
    original_hash = vol.password_hash
    session = _session_returning(vol)  # реальный get_by_id вернёт этого волонтёра

    # SMTP не настроен → send_email бросает ValidationError → email_sent=False (честно).
    with patch(
        "app.services.volunteer.smtp_service.send_email",
        new=AsyncMock(side_effect=ValidationError("SMTP не настроен")),
    ):
        email, email_sent, token, reset_url = await vol_service.admin_reset_password(
            session, vol.id
        )

    assert email == vol.email
    assert email_sent is False  # SMTP не настроен → письмо не ушло (честно)
    # Токен реально валиден: декодится к id волонтёра с purpose reset_password
    assert decode_purpose_token(token, "reset_password") == str(vol.id)
    assert token in reset_url
    assert vol.password_hash == original_hash  # пароль НЕ тронут (только ссылка сброса)


@pytest.mark.asyncio
async def test_service_admin_reset_password_not_found_404():
    """Нет волонтёра с таким id → NotFoundError (404) из get_by_id."""
    session = _no_existing_session()  # scalar_one_or_none() → None
    with pytest.raises(NotFoundError):
        await vol_service.admin_reset_password(session, uuid4())


@pytest.mark.asyncio
async def test_admin_reset_volunteer_password_endpoint_returns_link_when_not_sent(client):
    """Эндпоинт (admin): письмо не ушло → reset_url/reset_token в ответе (без фейка)."""
    with patch(
        "app.services.volunteer.admin_reset_password",
        new=AsyncMock(
            return_value=(
                "vol@example.com",
                False,
                "tok123",
                "https://ecopulse.reo.ru/reset?token=tok123",
            )
        ),
    ):
        resp = await client.post(f"/api/v1/volunteers/{uuid4()}/reset-password")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["email"] == "vol@example.com"
    assert body["email_sent"] is False
    assert body["reset_token"] == "tok123"
    assert body["reset_url"].endswith("tok123")


@pytest.mark.asyncio
async def test_admin_reset_volunteer_password_endpoint_hides_token_when_sent(client):
    """Эндпоинт (admin): письмо ушло (email_sent=true) → токен/ссылку в ответ НЕ кладём."""
    with patch(
        "app.services.volunteer.admin_reset_password",
        new=AsyncMock(return_value=("vol@example.com", True, "tok123", "https://x/reset?token=tok123")),
    ):
        resp = await client.post(f"/api/v1/volunteers/{uuid4()}/reset-password")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email_sent"] is True
    assert body["reset_token"] is None
    assert body["reset_url"] is None


@pytest.mark.asyncio
async def test_admin_reset_volunteer_password_404(client):
    """Нет волонтёра → 404 NOT_FOUND (проброс NotFoundError из сервиса)."""
    with patch(
        "app.services.volunteer.admin_reset_password",
        new=AsyncMock(side_effect=NotFoundError("Волонтёр")),
    ):
        resp = await client.post(f"/api/v1/volunteers/{uuid4()}/reset-password")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_admin_reset_volunteer_password_forbidden_for_non_admin(client):
    """Не-admin → 403 (гейт require_admin на роутере /volunteers)."""
    async def _deny():
        raise ForbiddenError("Требуется роль администратора")

    app.dependency_overrides[require_admin] = _deny
    try:
        resp = await client.post(f"/api/v1/volunteers/{uuid4()}/reset-password")
    finally:
        # Вернём проходной override из фикстуры client (teardown всё равно очистит).
        app.dependency_overrides[require_admin] = lambda: None
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_reset_volunteer_password_unauthenticated_401(client):
    """Гейт require_admin: невалидный Bearer-токен → 401 (реальный get_current_user)."""
    # Снимаем проходные override'ы, чтобы отработала настоящая auth-цепочка.
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(get_current_user, None)
    try:
        resp = await client.post(
            f"/api/v1/volunteers/{uuid4()}/reset-password",
            headers={"Authorization": "Bearer garbage.token.value"},
        )
    finally:
        # teardown фикстуры client всё равно очистит overrides.
        app.dependency_overrides[require_admin] = lambda: None
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_get_current_actor_accepts_admin_and_volunteer():
    """get_current_actor пускает АДМИНА (access-токен → users) И ВОЛОНТЁРА (typ=volunteer →
    volunteers). Ключевое: волонтёрский токен на READ-эндпоинтах МНО больше НЕ даёт 401.
    Чужой валидный токен (refresh) — ни то, ни другое → 401."""
    from app.core.errors import AppError
    from app.core.security import (
        create_access_token,
        create_refresh_token,
        create_volunteer_access_token,
    )
    from app.deps import get_current_actor

    # Админ (access-токен → users).
    admin = SimpleNamespace(id=uuid4(), is_active=True)
    res_a = MagicMock()
    res_a.scalar_one_or_none.return_value = admin
    sess_a = AsyncMock()
    sess_a.execute = AsyncMock(return_value=res_a)
    tok_a = create_access_token({"sub": str(admin.id)})
    assert await get_current_actor(SimpleNamespace(credentials=tok_a), sess_a) is admin

    # Волонтёр (typ=volunteer → volunteers).
    vol = SimpleNamespace(id=uuid4(), is_active=True)
    res_v = MagicMock()
    res_v.scalar_one_or_none.return_value = vol
    sess_v = AsyncMock()
    sess_v.execute = AsyncMock(return_value=res_v)
    tok_v = create_volunteer_access_token(str(vol.id))
    assert await get_current_actor(SimpleNamespace(credentials=tok_v), sess_v) is vol

    # Refresh-токен — не access и не volunteer → 401 (сессия даже не запрашивается).
    tok_r = create_refresh_token({"sub": str(uuid4())})
    with pytest.raises(AppError) as exc:
        await get_current_actor(SimpleNamespace(credentials=tok_r), AsyncMock())
    assert exc.value.status_code == 401
