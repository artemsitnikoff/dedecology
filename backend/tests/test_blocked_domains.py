"""Тесты справочника «Стоп-лист почтовых доменов»: нормализация/CRUD DB-сервиса,
админ-роуты /blocked-domains (только admin) и блокировка регистрации волонтёра по домену."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.permissions import require_admin
from app.deps import get_current_actor, get_current_user
from app.main import app
from app.models import BlockedEmailDomain, User, Volunteer
from app.schemas.volunteer import VolunteerRegister
from app.services import blocked_domain as bd_service
from app.services import volunteer as vol_service


def _orm_domain(domain="gmail.com") -> BlockedEmailDomain:
    """ORM-объект BlockedEmailDomain в памяти (id — server_default в БД, ставим сами)."""
    d = BlockedEmailDomain(domain=domain)
    d.id = uuid4()
    return d


# --- _normalize ----------------------------------------------------------------


def test_normalize_lowercases_and_strips():
    assert bd_service._normalize("  GMAIL.COM ") == "gmail.com"


def test_normalize_strips_leading_at():
    assert bd_service._normalize("@Gmail.com") == "gmail.com"


def test_normalize_extracts_domain_from_email():
    assert bd_service._normalize("User@Sub.Example.COM") == "sub.example.com"


# --- Сервис CRUD (session — мок, без живой БД) ---------------------------------


@pytest.mark.asyncio
async def test_service_create_domain_normalizes():
    """create нормализует '  GMAIL.COM ' → 'gmail.com' (дубля нет)."""
    dup_res = MagicMock()
    dup_res.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=dup_res)
    session.add = MagicMock()

    created = await bd_service.create_domain(session, "  GMAIL.COM ")
    assert created.domain == "gmail.com"
    session.add.assert_called_once_with(created)
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_create_domain_normalizes_at_form():
    """create нормализует '@Gmail.com' → 'gmail.com'."""
    dup_res = MagicMock()
    dup_res.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=dup_res)
    session.add = MagicMock()

    created = await bd_service.create_domain(session, "@Gmail.com")
    assert created.domain == "gmail.com"


@pytest.mark.asyncio
async def test_service_create_domain_duplicate_conflict():
    """Существующий домен → ConflictError (409)."""
    dup_res = MagicMock()
    dup_res.scalar_one_or_none.return_value = uuid4()  # домен занят
    session = AsyncMock()
    session.execute = AsyncMock(return_value=dup_res)

    with pytest.raises(ConflictError):
        await bd_service.create_domain(session, "gmail.com")


@pytest.mark.asyncio
async def test_service_create_domain_without_dot_validation():
    """Домен без точки → ValidationError (400), БД не трогается."""
    session = AsyncMock()
    with pytest.raises(ValidationError):
        await bd_service.create_domain(session, "localhost")
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_service_create_domain_empty_validation():
    """Пустой домен → ValidationError (400)."""
    session = AsyncMock()
    with pytest.raises(ValidationError):
        await bd_service.create_domain(session, "   ")
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_service_delete_domain_not_found():
    """delete отсутствующего id → NotFoundError (404)."""
    get_res = MagicMock()
    get_res.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=get_res)

    with pytest.raises(NotFoundError):
        await bd_service.delete_domain(session, uuid4())


@pytest.mark.asyncio
async def test_service_delete_domain_ok():
    """delete найденного домена → session.delete вызван."""
    target = _orm_domain()
    get_res = MagicMock()
    get_res.scalar_one_or_none.return_value = target
    session = AsyncMock()
    session.execute = AsyncMock(return_value=get_res)
    session.delete = AsyncMock()

    await bd_service.delete_domain(session, target.id)
    session.delete.assert_awaited_once_with(target)


@pytest.mark.asyncio
async def test_service_list_domains():
    """list_domains возвращает список ORM-объектов (упорядочен запросом)."""
    domains = [_orm_domain("a.com"), _orm_domain("b.com")]
    res = MagicMock()
    res.scalars.return_value.all.return_value = domains
    session = AsyncMock()
    session.execute = AsyncMock(return_value=res)

    result = await bd_service.list_domains(session)
    assert [d.domain for d in result] == ["a.com", "b.com"]


# --- is_email_blocked ----------------------------------------------------------


@pytest.mark.asyncio
async def test_is_email_blocked_true_for_listed_domain():
    """Домен адреса присутствует в стоп-листе (сид, напр. gmail.com) → True."""
    res = MagicMock()
    res.scalar.return_value = True
    session = AsyncMock()
    session.execute = AsyncMock(return_value=res)

    assert await bd_service.is_email_blocked(session, "Someone@Gmail.com") is True


@pytest.mark.asyncio
async def test_is_email_blocked_false_for_russian_domain():
    """Российский домен (mail.ru) не в стоп-листе → False."""
    res = MagicMock()
    res.scalar.return_value = False
    session = AsyncMock()
    session.execute = AsyncMock(return_value=res)

    assert await bd_service.is_email_blocked(session, "user@mail.ru") is False


@pytest.mark.asyncio
async def test_is_email_blocked_no_at_returns_false():
    """Строка без '@' → False, БД не дёргается."""
    session = AsyncMock()
    assert await bd_service.is_email_blocked(session, "notanemail") is False
    session.execute.assert_not_called()


# --- Админ-роуты /blocked-domains ----------------------------------------------


@pytest.mark.asyncio
async def test_list_blocked_domains(client):
    """GET /blocked-domains → [{id, domain, created_at}]."""
    from datetime import datetime, timezone

    d = _orm_domain("gmail.com")
    d.created_at = datetime.now(timezone.utc)
    with patch(
        "app.api.v1.blocked_domains.blocked_domain_service.list_domains",
        new=AsyncMock(return_value=[d]),
    ):
        resp = await client.get("/api/v1/blocked-domains")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["domain"] == "gmail.com"
    assert "id" in body[0]
    assert "created_at" in body[0]


@pytest.mark.asyncio
async def test_create_blocked_domain_201(client):
    """POST /blocked-domains → 201, домен передан в сервис."""
    from datetime import datetime, timezone

    created = _orm_domain("proton.me")
    created.created_at = datetime.now(timezone.utc)
    spy = AsyncMock(return_value=created)
    with patch(
        "app.api.v1.blocked_domains.blocked_domain_service.create_domain", new=spy
    ):
        resp = await client.post("/api/v1/blocked-domains", json={"domain": "proton.me"})
    assert resp.status_code == 201
    assert resp.json()["domain"] == "proton.me"
    assert spy.call_args.kwargs["domain"] == "proton.me"


@pytest.mark.asyncio
async def test_create_blocked_domain_duplicate_409(client):
    """POST дубль → ConflictError (409)."""
    with patch(
        "app.api.v1.blocked_domains.blocked_domain_service.create_domain",
        new=AsyncMock(side_effect=ConflictError("Домен «gmail.com» уже в стоп-листе")),
    ):
        resp = await client.post("/api/v1/blocked-domains", json={"domain": "gmail.com"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_create_blocked_domain_requires_body_422(client):
    """domain обязателен (min_length=1) → пустое тело = 422."""
    resp = await client.post("/api/v1/blocked-domains", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_blocked_domain_204(client):
    """DELETE /blocked-domains/{id} → 204."""
    with patch(
        "app.api.v1.blocked_domains.blocked_domain_service.delete_domain",
        new=AsyncMock(return_value=None),
    ):
        resp = await client.delete(f"/api/v1/blocked-domains/{uuid4()}")
    assert resp.status_code == 204


# --- require_admin: не-админ → 403 / аноним → 401 ------------------------------


def _non_admin() -> User:
    u = User(
        email="user@dedekolog.ru",
        password_hash="x",
        fio="Рядовой Пользователь",
        role="user",
        status="active",
        is_active=True,
        is_superadmin=False,
    )
    u.id = uuid4()
    return u


@pytest.mark.asyncio
async def test_list_blocked_domains_forbidden_for_non_admin(client):
    """GET /blocked-domains не-админом → 403 (реальный require_admin)."""
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides[get_current_user] = lambda: _non_admin()
    resp = await client.get("/api/v1/blocked-domains")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_create_blocked_domain_forbidden_for_non_admin(client):
    """POST /blocked-domains не-админом → 403."""
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides[get_current_user] = lambda: _non_admin()
    resp = await client.post("/api/v1/blocked-domains", json={"domain": "gmail.com"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_blocked_domain_forbidden_for_non_admin(client):
    """DELETE /blocked-domains/{id} не-админом → 403."""
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides[get_current_user] = lambda: _non_admin()
    resp = await client.delete(f"/api/v1/blocked-domains/{uuid4()}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_blocked_domains_anonymous_401(client):
    """Без токена (сняты оверрайды auth) → 401 NOT_AUTHENTICATED."""
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_actor, None)
    resp = await client.get("/api/v1/blocked-domains")
    assert resp.status_code == 401


# --- Блокировка регистрации волонтёра по домену --------------------------------


@pytest.mark.asyncio
async def test_register_blocked_domain_400(client):
    """POST /volunteer/register с адресом на заблокированном домене → 400 EMAIL_DOMAIN_BLOCKED."""
    with patch(
        "app.services.blocked_domain.is_email_blocked",
        new=AsyncMock(return_value=True),
    ):
        resp = await client.post(
            "/api/v1/volunteer/register",
            json={
                "email": "someone@gmail.com",
                "password": "secret123",
                "repeat_password": "secret123",
            },
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "EMAIL_DOMAIN_BLOCKED"


@pytest.mark.asyncio
async def test_register_allowed_domain_not_blocked():
    """Регистрация на mail.ru (не в стоп-листе) не падает по EMAIL_DOMAIN_BLOCKED."""
    session = MagicMock()
    no_dup = MagicMock()
    no_dup.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=no_dup)
    session.add = MagicMock()
    session.flush = AsyncMock()
    data = VolunteerRegister(
        email="user@mail.ru", password="secret123", repeat_password="secret123"
    )
    with patch(
        "app.services.blocked_domain.is_email_blocked",
        new=AsyncMock(return_value=False),
    ):
        vol = await vol_service.register(session, data)
    assert isinstance(vol, Volunteer)
    assert vol.email == "user@mail.ru"
