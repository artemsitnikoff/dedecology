"""Тесты SMTP-настроек — офлайн (без сети/БД).

Сервисный слой мокается в endpoint-тестах; юнит-тесты сервиса гоняют логику на
поддельной AsyncMock-сессии (стиль tests/test_mno.py). Реальный smtplib не
вызывается — send_via_smtp мокается. Ключевые инварианты: пароль наружу не течёт,
write-only merge пароля, честная фиксация исхода теста.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.crypto import encrypt_text, decrypt_text
from app.core.errors import AppError, ValidationError
from app.models import SmtpSettings
from app.services import smtp as smtp_service


# --- crypto round-trip ---------------------------------------------------------


def test_crypto_round_trip():
    """encrypt_text/decrypt_text — обратимы; шифртекст не равен открытому тексту."""
    secret = "s3cr3t-пароль"
    token = encrypt_text(secret)
    assert token != secret
    assert decrypt_text(token) == secret


def test_crypto_decrypt_garbage_raises():
    """Битый токен → ValidationError (а не молчаливый мусор)."""
    with pytest.raises(ValidationError):
        decrypt_text("не-настоящий-токен")


# --- save_config: валидации + write-only merge пароля --------------------------


def _row(**kw) -> SmtpSettings:
    base = dict(
        host="smtp.example.com",
        port=465,
        encryption="ssl",
        username="user@example.com",
        password_enc=encrypt_text("old-password"),
        from_email="noreply@example.com",
        from_name="ЭкоПульс",
        status="connected",
        last_test_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
        last_test_ok=True,
        last_test_error=None,
    )
    base.update(kw)
    row = SmtpSettings(**base)
    row.id = kw.get("id", uuid4())
    return row


def _session_with(row):
    """AsyncMock-сессия, у которой _get() (select().limit(1)) вернёт row (или None)."""
    res = MagicMock()
    res.scalar_one_or_none.return_value = row
    session = AsyncMock()
    session.execute = AsyncMock(return_value=res)
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_save_config_rejects_bad_port():
    session = _session_with(None)
    with pytest.raises(ValidationError):
        await smtp_service.save_config(
            session, uuid4(),
            host="smtp.example.com", port=70000, encryption="ssl",
            username="u", password="p", from_email="a@b.ru", from_name="",
        )


@pytest.mark.asyncio
async def test_save_config_rejects_bad_email():
    session = _session_with(None)
    with pytest.raises(ValidationError):
        await smtp_service.save_config(
            session, uuid4(),
            host="smtp.example.com", port=465, encryption="ssl",
            username="u", password="p", from_email="not-an-email", from_name="",
        )


@pytest.mark.asyncio
async def test_save_config_rejects_empty_host():
    session = _session_with(None)
    with pytest.raises(ValidationError):
        await smtp_service.save_config(
            session, uuid4(),
            host="   ", port=465, encryption="ssl",
            username="u", password="p", from_email="a@b.ru", from_name="",
        )


@pytest.mark.asyncio
async def test_save_config_rejects_bad_encryption():
    session = _session_with(None)
    with pytest.raises(ValidationError):
        await smtp_service.save_config(
            session, uuid4(),
            host="smtp.example.com", port=465, encryption="quantum",
            username="u", password="p", from_email="a@b.ru", from_name="",
        )


@pytest.mark.asyncio
async def test_save_config_new_row_requires_password():
    """Новая конфигурация без пароля (старого нет) → ValidationError."""
    session = _session_with(None)
    with pytest.raises(ValidationError):
        await smtp_service.save_config(
            session, uuid4(),
            host="smtp.example.com", port=465, encryption="ssl",
            username="u", password="", from_email="a@b.ru", from_name="",
        )


@pytest.mark.asyncio
async def test_save_config_empty_password_keeps_old():
    """Пустой пароль при существующей строке → старый password_enc сохраняется."""
    old_enc = encrypt_text("old-password")
    row = _row(password_enc=old_enc)
    session = _session_with(row)

    result = await smtp_service.save_config(
        session, uuid4(),
        host="smtp.new.com", port=587, encryption="tls",
        username="user2", password="", from_email="new@b.ru", from_name="ЭкоПульс",
    )

    assert result.password_enc == old_enc  # пароль НЕ перезаписан
    assert result.host == "smtp.new.com"
    assert result.encryption == "tls"
    # Любое сохранение сбрасывает verified.
    assert result.status == "disconnected"
    assert result.last_test_ok is False
    assert result.last_test_at is None
    # Строка уже была — новую SmtpSettings не создаём (session.add вызывается лишь
    # для аудит-записи, но не для SmtpSettings).
    added_types = [type(c.args[0]) for c in session.add.call_args_list]
    assert SmtpSettings not in added_types


@pytest.mark.asyncio
async def test_save_config_new_password_encrypted():
    """Непустой пароль → шифруется (в БД не открытым текстом), расшифровывается обратно."""
    row = _row()
    session = _session_with(row)

    result = await smtp_service.save_config(
        session, uuid4(),
        host="smtp.example.com", port=465, encryption="ssl",
        username="u", password="brand-new-pass", from_email="a@b.ru", from_name="",
    )

    assert result.password_enc != "brand-new-pass"
    assert decrypt_text(result.password_enc) == "brand-new-pass"


# --- get_status: пароль НЕ отдаётся --------------------------------------------


@pytest.mark.asyncio
async def test_get_status_not_configured():
    session = _session_with(None)
    status = await smtp_service.get_status(session)
    assert status["configured"] is False
    assert status["verified"] is False
    assert "password" not in status
    assert "password_enc" not in status


@pytest.mark.asyncio
async def test_get_status_never_leaks_password():
    row = _row()
    session = _session_with(row)
    status = await smtp_service.get_status(session)

    assert status["configured"] is True
    assert status["verified"] is True  # status=='connected' и last_test_ok
    assert status["host"] == "smtp.example.com"
    assert status["from_email"] == "noreply@example.com"
    assert status["last_test_at"] == "2026-07-01T10:00:00+00:00"
    # Пароль (ни открытый, ни зашифрованный) в статусе отсутствует.
    for key, value in status.items():
        assert "password" not in key
    assert row.password_enc not in status.values()


# --- send_test_email: успех / сбой ---------------------------------------------


@pytest.mark.asyncio
async def test_send_test_email_success_marks_ok():
    """Успешная отправка → last_test_ok=True, status='connected', commit вызван."""
    row = _row(status="disconnected", last_test_ok=False)
    session = _session_with(row)

    with patch("app.services.smtp.send_via_smtp", new=AsyncMock()) as sender:
        result = await smtp_service.send_test_email(session, uuid4(), to="dest@example.com")

    sender.assert_awaited_once()
    assert row.last_test_ok is True
    assert row.status == "connected"
    assert row.last_test_error is None
    assert result["sent_to"] == "dest@example.com"
    session.commit.assert_awaited()  # сервис коммитит сам


@pytest.mark.asyncio
async def test_send_test_email_failure_records_error_and_raises():
    """Сбой отправки → last_test_error проставлен, status='disconnected', commit, исключение проброшено."""
    row = _row(status="connected", last_test_ok=True)
    session = _session_with(row)

    boom = AppError(code="SMTP_AUTH_ERROR", message="Неверный логин", status_code=400)
    with patch("app.services.smtp.send_via_smtp", new=AsyncMock(side_effect=boom)):
        with pytest.raises(AppError):
            await smtp_service.send_test_email(session, uuid4(), to="dest@example.com")

    assert row.last_test_ok is False
    assert row.status == "disconnected"
    assert row.last_test_error == "Неверный логин"  # честная причина (AppError.message)
    session.commit.assert_awaited()  # исход сохранён даже при сбое


@pytest.mark.asyncio
async def test_send_test_email_rejects_bad_to():
    row = _row()
    session = _session_with(row)
    with pytest.raises(ValidationError):
        await smtp_service.send_test_email(session, uuid4(), to="garbage")


@pytest.mark.asyncio
async def test_send_test_email_requires_configured():
    """SMTP не настроен → ValidationError (host пуст)."""
    session = _session_with(None)
    with pytest.raises(ValidationError):
        await smtp_service.send_test_email(session, uuid4(), to="dest@example.com")


# --- disconnect ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_disconnect_resets_status():
    row = _row(status="connected", last_test_ok=True)
    session = _session_with(row)
    await smtp_service.disconnect(session, uuid4())
    assert row.status == "disconnected"
    assert row.last_test_ok is False


@pytest.mark.asyncio
async def test_disconnect_requires_configured():
    session = _session_with(None)
    with pytest.raises(ValidationError):
        await smtp_service.disconnect(session, uuid4())


# --- Эндпоинты (сервис замокан) ------------------------------------------------


_STATUS = {
    "configured": True,
    "verified": False,
    "host": "smtp.example.com",
    "port": 465,
    "encryption": "ssl",
    "username": "user@example.com",
    "from_email": "noreply@example.com",
    "from_name": "ЭкоПульс",
    "last_test_at": None,
    "last_test_ok": False,
    "last_test_error": None,
}


@pytest.mark.asyncio
async def test_get_smtp_status_endpoint(client):
    with patch(
        "app.api.v1.smtp.smtp_service.get_status",
        new=AsyncMock(return_value=_STATUS),
    ):
        resp = await client.get("/api/v1/settings/smtp")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["host"] == "smtp.example.com"
    assert "password" not in body


@pytest.mark.asyncio
async def test_save_smtp_config_endpoint(client):
    """POST /config → save_config + commit → возвращает статус."""
    save = AsyncMock(return_value=_row())
    with patch("app.api.v1.smtp.smtp_service.save_config", new=save), patch(
        "app.api.v1.smtp.smtp_service.get_status",
        new=AsyncMock(return_value=_STATUS),
    ):
        resp = await client.post(
            "/api/v1/settings/smtp/config",
            json={
                "host": "smtp.example.com",
                "port": 465,
                "encryption": "ssl",
                "username": "user@example.com",
                "password": "secret",
                "from_email": "noreply@example.com",
                "from_name": "ЭкоПульс",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["host"] == "smtp.example.com"
    save.assert_awaited_once()
    # Пароль передан в сервис как kwarg (наружу его не возвращаем).
    assert save.call_args.kwargs["password"] == "secret"


@pytest.mark.asyncio
async def test_save_smtp_config_endpoint_requires_fields(client):
    """Без host/port/from_email → 422 (обязательные поля схемы)."""
    resp = await client.post("/api/v1/settings/smtp/config", json={"username": "u"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_smtp_test_endpoint(client):
    with patch(
        "app.api.v1.smtp.smtp_service.send_test_email",
        new=AsyncMock(return_value={"sent_to": "dest@example.com", "last_test_at": "2026-07-08T00:00:00+00:00"}),
    ):
        resp = await client.post(
            "/api/v1/settings/smtp/test", json={"to": "dest@example.com"}
        )
    assert resp.status_code == 200
    assert resp.json()["sent_to"] == "dest@example.com"


@pytest.mark.asyncio
async def test_disconnect_smtp_endpoint(client):
    with patch(
        "app.api.v1.smtp.smtp_service.disconnect", new=AsyncMock(return_value=None)
    ):
        resp = await client.post("/api/v1/settings/smtp/disconnect")
    assert resp.status_code == 200
    assert resp.json()["message"] == "SMTP отключён"


@pytest.mark.asyncio
async def test_smtp_error_envelope(client):
    """AppError из сервиса → унифицированный конверт {error:{code,message,details}}."""
    boom = AppError(code="SMTP_AUTH_ERROR", message="Неверный логин", status_code=400)
    with patch(
        "app.api.v1.smtp.smtp_service.send_test_email", new=AsyncMock(side_effect=boom)
    ):
        resp = await client.post(
            "/api/v1/settings/smtp/test", json={"to": "dest@example.com"}
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "SMTP_AUTH_ERROR"


@pytest.mark.asyncio
async def test_smtp_requires_admin(client, current_user):
    """Гейт require_admin: не-админ (role='user') получает 403 FORBIDDEN.

    Снимаем override require_admin (в conftest он замкнут в no-op), возвращаем
    реальную зависимость — она читает current_user из get_current_user override.
    """
    from app.main import app
    from app.core.permissions import require_admin

    current_user.role = "user"
    app.dependency_overrides.pop(require_admin, None)
    try:
        resp = await client.get("/api/v1/settings/smtp")
    finally:
        app.dependency_overrides[require_admin] = lambda: None
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
