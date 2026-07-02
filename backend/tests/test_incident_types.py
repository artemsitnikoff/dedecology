"""Тесты справочника «Типы инцидентов»: дефолты-константа, DB-сервис CRUD,
публичный GET /intake/incident-types (из БД) и админ-роуты /incident-types."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.errors import ConflictError, NotFoundError
from app.core.permissions import require_admin
from app.deps import get_current_user
from app.main import app
from app.models import IncidentType, User
from app.services import incident_type as it_service
from app.services.incident_types import (
    INCIDENT_TYPES,
    incident_type_label,
    is_valid_incident_type,
    list_incident_types,
)

# Ожидаемые коды дефолтов в фиксированном порядке (снимок для сида миграции 0011).
_EXPECTED_CODES = [
    "no_access",
    "blocked_access",
    "no_container",
    "fire",
    "non_tko_in_container",
    "damaged_container",
    "waste_nearby",
    "non_tko_on_site",
    "overflow",
    "other",
]


def _orm_type(code="fire", label="Возгорание в контейнере", sort_order=3) -> IncidentType:
    """ORM-объект IncidentType в памяти (id проставляем сами — в БД это server_default)."""
    t = IncidentType(code=code, label=label, sort_order=sort_order)
    t.id = uuid4()
    return t


# --- Константа-дефолты (snapshot для миграции; из рантайма больше не читается) ---


def test_incident_types_defaults_ten_in_order():
    """10 дефолтов, порядок кодов фиксирован, у каждого непустой label."""
    assert len(INCIDENT_TYPES) == 10
    assert [t["code"] for t in INCIDENT_TYPES] == _EXPECTED_CODES
    assert all(t["label"].strip() for t in INCIDENT_TYPES)


def test_defaults_helpers_resolve():
    """Хелперы дефолтов (для справки/тестов): валидность и резолв подписи."""
    assert is_valid_incident_type("fire") is True
    assert is_valid_incident_type("nope") is False
    assert incident_type_label("other") == "Иное"
    assert incident_type_label(None) == ""
    assert list_incident_types()[0] == {
        "code": "no_access",
        "label": "Отсутствует доступ к МНО",
    }


# --- Сервис CRUD (session — мок, без живой БД) ---------------------------------


@pytest.mark.asyncio
async def test_service_list_types_orders_by_sort_then_code():
    """list_types возвращает список ORM-объектов (упорядочен запросом)."""
    types = [_orm_type(code="a", sort_order=0), _orm_type(code="b", sort_order=1)]
    res = MagicMock()
    res.scalars.return_value.all.return_value = types
    session = AsyncMock()
    session.execute = AsyncMock(return_value=res)

    result = await it_service.list_types(session)
    assert [t.code for t in result] == ["a", "b"]


@pytest.mark.asyncio
async def test_service_create_type_auto_code_and_sort():
    """Пустой code → автокод 'type_…'; sort_order по умолчанию = max+1."""
    exists_res = MagicMock()
    exists_res.scalar_one_or_none.return_value = None  # автокод свободен
    max_res = MagicMock()
    max_res.scalar_one_or_none.return_value = 9  # текущий максимум → next = 10
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[exists_res, max_res])
    session.add = MagicMock()

    created = await it_service.create_type(session, label="  Новый тип  ")
    assert created.code.startswith("type_")
    assert created.label == "Новый тип"  # обрезка/стрип
    assert created.sort_order == 10
    session.add.assert_called_once_with(created)


@pytest.mark.asyncio
async def test_service_create_type_explicit_sort_and_code():
    """Заданный уникальный code + явный sort_order сохраняются как есть."""
    exists_res = MagicMock()
    exists_res.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=exists_res)
    session.add = MagicMock()

    created = await it_service.create_type(
        session, label="Свалка", code="dump", sort_order=5
    )
    assert created.code == "dump"
    assert created.sort_order == 5


@pytest.mark.asyncio
async def test_service_create_type_duplicate_code_conflict():
    """Заданный code, уже существующий в БД → ConflictError (409)."""
    exists_res = MagicMock()
    exists_res.scalar_one_or_none.return_value = uuid4()  # код занят
    session = AsyncMock()
    session.execute = AsyncMock(return_value=exists_res)

    with pytest.raises(ConflictError):
        await it_service.create_type(session, label="Дубль", code="fire")


@pytest.mark.asyncio
async def test_service_update_type_changes_label_and_sort():
    """update_type правит label/sort_order; code не трогается."""
    target = _orm_type(code="fire", label="Старое", sort_order=3)
    get_res = MagicMock()
    get_res.scalar_one_or_none.return_value = target
    session = AsyncMock()
    session.execute = AsyncMock(return_value=get_res)

    updated = await it_service.update_type(
        session, target.id, label="Новое имя", sort_order=1
    )
    assert updated.code == "fire"  # код неизменяем
    assert updated.label == "Новое имя"
    assert updated.sort_order == 1


@pytest.mark.asyncio
async def test_service_update_type_not_found():
    """update_type по несуществующему id → NotFoundError (404)."""
    get_res = MagicMock()
    get_res.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=get_res)

    with pytest.raises(NotFoundError):
        await it_service.update_type(session, uuid4(), label="X")


@pytest.mark.asyncio
async def test_service_delete_type():
    """delete_type удаляет найденный тип (session.delete вызван)."""
    target = _orm_type()
    get_res = MagicMock()
    get_res.scalar_one_or_none.return_value = target
    session = AsyncMock()
    session.execute = AsyncMock(return_value=get_res)
    session.delete = AsyncMock()

    await it_service.delete_type(session, target.id)
    session.delete.assert_awaited_once_with(target)


@pytest.mark.asyncio
async def test_service_code_exists():
    """code_exists: непустой код с попаданием → True; пустой код → False (без запроса)."""
    hit_res = MagicMock()
    hit_res.scalar_one_or_none.return_value = uuid4()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=hit_res)

    assert await it_service.code_exists(session, "fire") is True
    # Пустой код короткозамыкается — БД не дёргается.
    assert await it_service.code_exists(session, "") is False
    assert session.execute.await_count == 1


# --- Публичный GET /intake/incident-types (теперь из БД) -----------------------


@pytest.mark.asyncio
async def test_public_incident_types_endpoint_from_db(client):
    """GET /intake/incident-types → [{code, label}] из БД (контракт сохранён)."""
    db_types = [
        _orm_type(code="fire", label="Возгорание в контейнере", sort_order=0),
        _orm_type(code="other", label="Иное", sort_order=1),
    ]
    with patch(
        "app.api.v1.intake.incident_type_service.list_types",
        new=AsyncMock(return_value=db_types),
    ):
        resp = await client.get("/api/v1/intake/incident-types")
    assert resp.status_code == 200
    data = resp.json()
    assert data == [
        {"code": "fire", "label": "Возгорание в контейнере"},
        {"code": "other", "label": "Иное"},
    ]


# --- Админ-роуты /incident-types -----------------------------------------------


@pytest.mark.asyncio
async def test_list_incident_types_full(client):
    """GET /incident-types → полный список [{id, code, label, sort_order}]."""
    db_types = [_orm_type(code="fire", label="Возгорание", sort_order=0)]
    with patch(
        "app.api.v1.incident_types.incident_type_service.list_types",
        new=AsyncMock(return_value=db_types),
    ):
        resp = await client.get("/api/v1/incident-types")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["code"] == "fire"
    assert body[0]["label"] == "Возгорание"
    assert body[0]["sort_order"] == 0
    assert "id" in body[0]


@pytest.mark.asyncio
async def test_create_incident_type(client):
    """POST /incident-types → 201, тело передано в сервис (label обязателен)."""
    created = _orm_type(code="type_abc123", label="Новый тип", sort_order=10)
    spy = AsyncMock(return_value=created)
    with patch("app.api.v1.incident_types.incident_type_service.create_type", new=spy):
        resp = await client.post("/api/v1/incident-types", json={"label": "Новый тип"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["label"] == "Новый тип"
    assert body["code"] == "type_abc123"
    assert spy.call_args.kwargs["label"] == "Новый тип"


@pytest.mark.asyncio
async def test_create_incident_type_requires_label_422(client):
    """label обязателен (min_length=1) → пустое тело/пустой label = 422."""
    resp = await client.post("/api/v1/incident-types", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_incident_type(client):
    """PATCH /incident-types/{id} → 200, label/sort_order переданы в сервис."""
    updated = _orm_type(code="fire", label="Переименовано", sort_order=2)
    spy = AsyncMock(return_value=updated)
    with patch("app.api.v1.incident_types.incident_type_service.update_type", new=spy):
        resp = await client.patch(
            f"/api/v1/incident-types/{uuid4()}",
            json={"label": "Переименовано", "sort_order": 2},
        )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Переименовано"
    assert spy.call_args.kwargs["label"] == "Переименовано"
    assert spy.call_args.kwargs["sort_order"] == 2


@pytest.mark.asyncio
async def test_delete_incident_type_204(client):
    """DELETE /incident-types/{id} → 204."""
    with patch(
        "app.api.v1.incident_types.incident_type_service.delete_type",
        new=AsyncMock(return_value=None),
    ):
        resp = await client.delete(f"/api/v1/incident-types/{uuid4()}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_update_incident_type_not_found_404(client):
    """PATCH несуществующего id → NotFoundError (404)."""
    with patch(
        "app.api.v1.incident_types.incident_type_service.update_type",
        new=AsyncMock(side_effect=NotFoundError("Тип инцидента")),
    ):
        resp = await client.patch(
            f"/api/v1/incident-types/{uuid4()}", json={"label": "X"}
        )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# --- require_admin: мутации не-админом → 403 -----------------------------------


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
async def test_create_incident_type_forbidden_for_non_admin(client):
    """POST /incident-types не-админом → 403 (реальный require_admin)."""
    # Снимаем оверрайд require_admin (пусть отработает настоящий) и подставляем
    # текущего пользователя с ролью user.
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides[get_current_user] = lambda: _non_admin()
    resp = await client.post("/api/v1/incident-types", json={"label": "Тип"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_incident_type_forbidden_for_non_admin(client):
    """DELETE /incident-types/{id} не-админом → 403."""
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides[get_current_user] = lambda: _non_admin()
    resp = await client.delete(f"/api/v1/incident-types/{uuid4()}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
