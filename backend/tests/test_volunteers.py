"""Тесты волонтёров — офлайн: сервис/токены реальные, session и внешние вызовы замоканы.

Покрывает: регистрацию (+дубль 409), подтверждение почты (валид/битый токен), логин
(успех / непроверенная почта 403 / блок 403 / неверный пароль 401), сброс пароля
(запрос+смена, токен-флоу), онбординг, изоляцию get_current_volunteer от admin-токена,
админ-справочник (list/active/delete + 403 для не-admin) и mailer без SMTP (False → токен).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.errors import (
    BlockedError,
    ConflictError,
    EmailNotVerifiedError,
    ForbiddenError,
    InvalidCredentialsError,
    InvalidTokenError,
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
from app.deps import get_current_volunteer
from app.main import app
from app.models import Volunteer
from app.schemas.volunteer import VolunteerRegister
from app.services import volunteer as vol_service


def _volunteer(email_verified=True, is_active=True, phone=None, last_seen_at=None):
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
async def test_register_returns_token_when_email_not_sent(client):
    """SMTP не настроен → email_sent=false и verify-токен/ссылка в ответе (честно, без фейка)."""
    vol = _volunteer(email_verified=False)
    with patch("app.api.v1.volunteer.register", new=AsyncMock(return_value=vol)):
        resp = await client.post(
            "/api/v1/volunteer/register",
            json={"email": "vol@example.com", "password": "secret123"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["volunteer_id"] == str(vol.id)
    assert body["email"] == "vol@example.com"
    assert body["email_sent"] is False
    assert body["email_verify_token"]  # токен присутствует
    assert body["verify_url"].endswith(body["email_verify_token"])
    # Токен реально валиден: декодится к id волонтёра с purpose verify_email
    assert decode_purpose_token(body["email_verify_token"], "verify_email") == str(vol.id)


@pytest.mark.asyncio
async def test_register_duplicate_email_409(client):
    with patch(
        "app.api.v1.volunteer.register",
        new=AsyncMock(side_effect=ConflictError("Волонтёр с таким email уже зарегистрирован")),
    ):
        resp = await client.post(
            "/api/v1/volunteer/register",
            json={"email": "dup@example.com", "password": "secret123"},
        )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_register_short_password_422(client):
    resp = await client.post(
        "/api/v1/volunteer/register",
        json={"email": "x@example.com", "password": "abc"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_verify_email_valid(client):
    vol = _volunteer(email_verified=True)
    with patch("app.api.v1.volunteer.verify_email", new=AsyncMock(return_value=vol)):
        resp = await client.post("/api/v1/volunteer/verify-email", json={"token": "good"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["email_verified"] is True


@pytest.mark.asyncio
async def test_verify_email_invalid_token_400(client):
    with patch(
        "app.api.v1.volunteer.verify_email",
        new=AsyncMock(side_effect=InvalidTokenError()),
    ):
        resp = await client.post("/api/v1/volunteer/verify-email", json={"token": "broken"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_TOKEN"


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
    with patch(
        "app.api.v1.volunteer.request_password_reset", new=AsyncMock(return_value=vol)
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
# Админ-справочник /volunteers (require_admin)
# =========================================================================


@pytest.mark.asyncio
async def test_admin_list_volunteers(client):
    vol = _volunteer(phone="+79990001122")
    with patch("app.services.volunteer.list_all", new=AsyncMock(return_value=[vol])):
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
# Токены и mailer — реальная логика
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


def test_mailer_returns_false_without_smtp():
    from app.services.mailer import deliver_email

    # В тестовом окружении SMTP_* пусты → письмо не отправляется, честный False.
    assert deliver_email("vol@example.com", "Тема", "Тело") is False


# =========================================================================
# Сервисный слой — реальная логика (session замокан)
# =========================================================================


@pytest.mark.asyncio
async def test_service_register_hashes_password_and_sets_flags():
    session = _no_existing_session()
    data = VolunteerRegister(email="vol@example.com", password="secret123")
    vol = await vol_service.register(session, data)
    assert vol.email_verified is False
    assert vol.is_active is True
    assert vol.phone is None
    assert verify_password("secret123", vol.password_hash) is True
    assert verify_password("wrong", vol.password_hash) is False


@pytest.mark.asyncio
async def test_service_register_duplicate_conflict():
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _volunteer()  # email уже есть
    session.execute = AsyncMock(return_value=result)
    data = VolunteerRegister(email="vol@example.com", password="secret123")
    with pytest.raises(ConflictError):
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


@pytest.mark.asyncio
async def test_service_verify_email_token_flow():
    session = MagicMock()
    session.flush = AsyncMock()
    vol = _volunteer(email_verified=False)
    good = create_purpose_token(str(vol.id), "verify_email", timedelta(hours=1))
    with patch("app.services.volunteer.get_by_id", new=AsyncMock(return_value=vol)):
        result = await vol_service.verify_email(session, good)
    assert result.email_verified is True

    # битый токен → InvalidTokenError (get_by_id даже не вызывается)
    with pytest.raises(InvalidTokenError):
        await vol_service.verify_email(session, "garbage")


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
