"""Тесты защитных фиксов Telegram-бота (после adversarial-ревью):
редакция токена в логах, санитайз ошибок Telegram API, SecretStr для INTAKE_TOKEN,
проверка владельца callback (чужой пользователь не может рулить чужим диалогом).
"""

from __future__ import annotations

import logging

import httpx
import pytest
from pydantic import SecretStr

from telegrambot import bot as botmod
from telegrambot.config import settings
from telegrambot.session import NO_MNO, PendingReport, encode_payload, new_pending_id
from telegrambot.tgapi import TelegramAPI


# --- get_updates: HTTP-ошибка санитизируется, токен НЕ утекает ---------------


async def test_get_updates_http_error_sanitized_no_token():
    """401 от Telegram → чистая httpx-ошибка без URL с токеном (иначе токен в трейсбеке)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    api = TelegramAPI("SECRET123", transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPError) as ei:
        await api.get_updates(offset=0, timeout=0)
    msg = str(ei.value)
    assert "SECRET123" not in msg
    assert "401" in msg
    # `from None` → исходное исключение с токеном подавлено (не печатается в трейсбеке).
    assert ei.value.__suppress_context__ is True


# --- download_file: ошибка не тащит токен в лог ------------------------------


async def test_download_file_error_does_not_log_token(caplog):
    """404 на скачивании файла → None, и токен НЕ попадает в текст лог-записи."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "/file/bot" in request.url.path:
            return httpx.Response(404, content=b"nope")
        return httpx.Response(
            200, json={"ok": True, "result": {"file_id": "F", "file_path": "photos/x.jpg"}}
        )

    api = TelegramAPI("SECRETTOK", transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.WARNING, logger="dedecology.telegrambot"):
        data = await api.download_by_file_id("F", max_bytes=1000)
    assert data is None
    assert caplog.records  # ошибка действительно залогирована
    assert all("SECRETTOK" not in r.getMessage() for r in caplog.records)


# --- Фильтр редакции токена (defense-in-depth) --------------------------------


def test_token_redacting_filter_masks_token():
    from telegrambot.main import _TokenRedactingFilter

    f = _TokenRedactingFilter("SEKRET")
    rec = logging.LogRecord(
        "dedecology.telegrambot",
        logging.ERROR,
        __file__,
        1,
        "url https://api.telegram.org/botSEKRET/getUpdates: boom",
        (),
        None,
    )
    assert f.filter(rec) is True
    assert "SEKRET" not in rec.getMessage()
    assert "<TOKEN>" in rec.getMessage()


# --- INTAKE_TOKEN — SecretStr (не светится в repr) ---------------------------


def test_intake_token_is_secret():
    assert isinstance(settings.INTAKE_TOKEN, SecretStr)
    # conftest ставит INTAKE_TOKEN=test-intake-token; значение — только через get_secret_value.
    assert settings.INTAKE_TOKEN.get_secret_value() == "test-intake-token"
    assert "test-intake-token" not in repr(settings.INTAKE_TOKEN)


# --- Проверка владельца callback: чужой user_id → отбой, без создания ---------


class _FakeAPI:
    """Минимальный фейк TelegramAPI: путь отбоя зовёт только answer_callback_query."""

    def __init__(self):
        self.answers: list = []

    async def answer_callback_query(self, cq_id, text=None, **kw):
        self.answers.append((cq_id, text))
        return {"ok": True}


async def test_callback_rejects_foreign_user():
    """Тап по кнопке от НЕ-владельца обращения → _CB_BAD_CHOICE, обращение не трогаем."""
    pid = new_pending_id()
    report = PendingReport(pending_id=pid, chat_id=100, user_id=100, candidates=[])
    botmod._STORE.put(report)
    try:
        fake = _FakeAPI()
        cq = {
            "id": "CB1",
            "data": encode_payload(pid, NO_MNO),
            "from": {"id": 999},  # НЕ владелец (report.user_id=100)
            "message": {"chat": {"id": 100}, "message_id": 5},
        }
        await botmod._on_callback(fake, cq)
        assert fake.answers == [("CB1", botmod._CB_BAD_CHOICE)]
        assert report.finalized is False
        assert report.processing is False
    finally:
        botmod._STORE.pop(pid)
