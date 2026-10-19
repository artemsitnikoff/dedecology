"""Тесты кнопки «➕ Добавить площадку» Telegram-бота (ADD_MNO, зеркало Макс-бота).

Покрывают:
  * intake_client.create_mno — ПУБЛИЧНЫЙ POST /intake/mno (без X-Intake-Token, honeypot
    website пуст), успех → {id,label}; не-2xx/сеть/не-JSON → None (без падения);
  * клавиатура выбора МНО: кнопка «➕ Добавить площадку» только при allow_add;
  * _compose_mno_address — адрес из полей разбора либо фолбэк на координаты;
  * полный путь колбэка ADD_MNO: замок ставится синхронно, фоновая задача создаёт МНО,
    привязывает его, помечает added_mno и переводит диалог к выбору типа.
"""

from __future__ import annotations

import httpx
import pytest

from telegrambot import bot as botmod
from telegrambot import intake_client as ic
from telegrambot.session import (
    ADD_MNO,
    NO_MNO,
    PendingReport,
    encode_payload,
    new_pending_id,
)


# ---------------------------------------------------------------------------
# intake_client.create_mno — публичный POST /intake/mno через MockTransport.
# ---------------------------------------------------------------------------


def _patch_httpx(monkeypatch, handler) -> None:
    """Подменить httpx.AsyncClient на вариант с MockTransport (оффлайн, без сети)."""
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


async def test_create_mno_success_public_no_token(monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = request.content
        # Бэк отдаёт MnoDetail: у волонтёрской площадки reg/name пустые.
        return httpx.Response(
            200,
            json={"id": "11111111-1111-1111-1111-111111111111", "reg": "", "name": ""},
        )

    _patch_httpx(monkeypatch, handler)
    out = await ic.create_mno(
        address="Московская обл., г. Голицыно, ул. Советская",
        coords="55.61, 36.98",
        name="",
        comment="Радар №7",
        photos=[b"JPEGBYTES"],
    )
    assert out is not None
    assert out["id"] == "11111111-1111-1111-1111-111111111111"
    # reg/name пусты → подпись падает на адрес.
    assert out["label"] == "Московская обл., г. Голицыно, ул. Советская"
    # Эндпоинт — публичный: X-Intake-Token НЕ шлём.
    assert seen["url"].endswith("/intake/mno")
    assert "x-intake-token" not in {k.lower() for k in seen["headers"]}
    # honeypot website присутствует и пуст; source=telegram; фото приложено.
    body = seen["body"]
    assert b'name="website"' in body
    assert b"telegram" in body
    assert b"JPEGBYTES" in body


async def test_create_mno_label_prefers_name_then_reg(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "abc", "reg": "", "name": "Площадка у дома"})

    _patch_httpx(monkeypatch, handler)
    out = await ic.create_mno(address="ул. Тестовая", coords="55.0, 37.0")
    assert out == {"id": "abc", "label": "Площадка у дома"}


async def test_create_mno_non_2xx_returns_none(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": "VALIDATION_ERROR"}})

    _patch_httpx(monkeypatch, handler)
    out = await ic.create_mno(address="", coords="", photos=[])
    assert out is None  # не падает — возвращает None


async def test_create_mno_network_error_returns_none(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    _patch_httpx(monkeypatch, handler)
    out = await ic.create_mno(address="ул. Тестовая", coords="55.0, 37.0")
    assert out is None


async def test_create_mno_missing_id_returns_none(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"reg": "", "name": "нет id"})

    _patch_httpx(monkeypatch, handler)
    out = await ic.create_mno(address="ул. Тестовая", coords="55.0, 37.0")
    assert out is None


# ---------------------------------------------------------------------------
# Клавиатура выбора МНО: кнопка «➕ Добавить площадку» только при allow_add.
# ---------------------------------------------------------------------------


def _all_buttons(kb: dict) -> list[tuple[str, str]]:
    return [(b["text"], b["callback_data"]) for row in kb["inline_keyboard"] for b in row]


def test_keyboard_add_button_present_when_allowed():
    pid = new_pending_id()
    kb = botmod._build_mno_keyboard(pid, [{"reg": "78-1", "name": "A"}], allow_add=True)
    btns = _all_buttons(kb)
    assert (botmod._ADD_MNO_BUTTON, encode_payload(pid, ADD_MNO)) in btns
    # «Нет в списке» тоже на месте.
    assert any(data == encode_payload(pid, NO_MNO) for _, data in btns)


def test_keyboard_add_button_absent_when_not_allowed():
    pid = new_pending_id()
    kb = botmod._build_mno_keyboard(pid, [{"reg": "78-1", "name": "A"}], allow_add=False)
    btns = _all_buttons(kb)
    assert all(data != encode_payload(pid, ADD_MNO) for _, data in btns)


def test_keyboard_add_button_present_with_empty_candidates():
    pid = new_pending_id()
    kb = botmod._build_mno_keyboard(pid, [], allow_add=True)
    btns = _all_buttons(kb)
    assert (botmod._ADD_MNO_BUTTON, encode_payload(pid, ADD_MNO)) in btns
    # Пустой список → «Отправить без привязки».
    assert any(data == encode_payload(pid, NO_MNO) for _, data in btns)


# ---------------------------------------------------------------------------
# _compose_mno_address.
# ---------------------------------------------------------------------------


def test_compose_address_from_parts():
    addr = botmod._compose_mno_address(
        {"region": "Моск. обл.", "city": "Голицыно", "street": "ул. Советская", "coords": "55,37"}
    )
    assert addr == "Моск. обл., Голицыно, ул. Советская"


def test_compose_address_falls_back_to_coords():
    # Гео-кнопка: адресных полей нет → фолбэк на строку координат.
    addr = botmod._compose_mno_address({"region": "", "city": "", "street": "", "coords": "55.6, 37.0"})
    assert addr == "55.6, 37.0"


# ---------------------------------------------------------------------------
# Полный путь колбэка ADD_MNO.
# ---------------------------------------------------------------------------


class _FakeAPI:
    """Фейк TelegramAPI: записывает вызовы, нужные пути ADD_MNO (answer/delete/send)."""

    def __init__(self):
        self.answers: list = []
        self.deleted: list = []
        self.messages: list = []

    async def answer_callback_query(self, cq_id, text=None, **kw):
        self.answers.append((cq_id, text))
        return {"ok": True}

    async def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))
        return {"ok": True}

    async def send_message(self, chat_id, text, **kw):
        self.messages.append((chat_id, text, kw.get("reply_markup")))
        return {"ok": True, "result": {"message_id": 999}}


async def test_add_mno_callback_full_flow(monkeypatch):
    """Тап «➕ Добавить площадку»: синхронный замок + фон создаёт МНО → выбор типа."""
    pid = new_pending_id()
    report = PendingReport(
        pending_id=pid,
        chat_id=100,
        user_id=100,
        photos=[b"PHOTO"],
        parsed={"coords": "55.61, 36.98", "comment": "Радар №7", "photo_time": "2026-10-19T10:00"},
        map_mid=777,
        # справочник типов уже под рукой (prefetch) → _advance_to_type покажет клавиатуру типа
        incident_types=[{"code": "overflow", "label": "Переполнение"}],
    )
    botmod._STORE.put(report)

    created_calls: list = []

    async def fake_create_mno(address, coords, name="", comment="", photos=None):
        created_calls.append(
            {"address": address, "coords": coords, "name": name, "comment": comment, "photos": photos}
        )
        return {"id": "MNO-NEW-1", "label": "ул. Советская"}

    monkeypatch.setattr(botmod, "create_mno", fake_create_mno)

    # _spawn перехватываем — собираем корутину и прогоняем детерминированно.
    spawned: list = []
    monkeypatch.setattr(botmod, "_spawn", lambda coro: spawned.append(coro))

    try:
        fake = _FakeAPI()
        cq = {
            "id": "CB-ADD",
            "data": encode_payload(pid, ADD_MNO),
            "from": {"id": 100},
            "message": {"chat": {"id": 100}, "message_id": 5},
        }
        await botmod._on_callback(fake, cq)

        # Замок шага 1 выставлен СИНХРОННО до фоновой задачи; create ещё не звали.
        assert report.awaiting_type is True
        assert len(spawned) == 1
        assert created_calls == []

        # Прогоняем фоновую задачу.
        await spawned[0]

        # МНО создано из нужных полей обращения (адрес из разбора, фото обращения).
        assert len(created_calls) == 1
        assert created_calls[0]["coords"] == "55.61, 36.98"
        assert created_calls[0]["photos"] == [b"PHOTO"]
        assert created_calls[0]["comment"] == "Радар №7"
        # Адрес собран из разобранных полей (здесь их нет) → фолбэк на координаты.
        assert created_calls[0]["address"] == "55.61, 36.98"

        # Привязка + пометка модерации.
        assert report.chosen_mno_id == "MNO-NEW-1"
        assert report.chosen_mno_label == "ул. Советская"
        assert report.added_mno is True

        # Тост «Создаю площадку…», удаление клавиатуры(5) и карты(777), показ выбора типа.
        assert ("CB-ADD", botmod._CB_ADD_MNO) in fake.answers
        assert (100, 5) in fake.deleted and (100, 777) in fake.deleted
        assert report.map_mid is None
        type_msgs = [m for m in fake.messages if m[1] == botmod._HDR_TYPE]
        assert type_msgs and type_msgs[0][2] is not None  # есть клавиатура типа
        # Обращение ещё НЕ финализировано — ждём выбора типа.
        assert report.finalized is False
    finally:
        botmod._STORE.pop(pid)


async def test_add_mno_callback_create_failure_rolls_back(monkeypatch):
    """create_mno вернул None → замок снят, мягкое сообщение, диалог не финализирован."""
    pid = new_pending_id()
    report = PendingReport(
        pending_id=pid,
        chat_id=100,
        user_id=100,
        photos=[b"PHOTO"],
        parsed={"coords": "55.61, 36.98"},
    )
    botmod._STORE.put(report)

    async def fake_create_mno(*a, **kw):
        return None

    monkeypatch.setattr(botmod, "create_mno", fake_create_mno)
    spawned: list = []
    monkeypatch.setattr(botmod, "_spawn", lambda coro: spawned.append(coro))

    try:
        fake = _FakeAPI()
        cq = {
            "id": "CB-ADD",
            "data": encode_payload(pid, ADD_MNO),
            "from": {"id": 100},
            "message": {"chat": {"id": 100}, "message_id": 5},
        }
        await botmod._on_callback(fake, cq)
        assert report.awaiting_type is True  # замок до фоновой задачи
        await spawned[0]

        # Откат: замок снят, добавления нет, обращение не финализировано.
        assert report.awaiting_type is False
        assert report.chosen_mno_id is None
        assert report.added_mno is False
        assert report.finalized is False
        assert any(m[1] == botmod._ADD_MNO_FAIL for m in fake.messages)
    finally:
        botmod._STORE.pop(pid)


async def test_add_mno_button_hidden_without_coords():
    """Нет координат обращения → кнопку «➕ Добавить площадку» не показываем."""
    pid = new_pending_id()
    report = PendingReport(
        pending_id=pid, chat_id=1, user_id=1, candidates=[{"id": "x", "reg": "78-1"}], parsed={}
    )

    sent: list = []

    class _CaptureAPI:
        async def send_photo(self, *a, **kw):
            return {"message_id": 1}

        async def send_message(self, chat_id, text, **kw):
            sent.append((text, kw.get("reply_markup")))
            return {"ok": True}

    # map не критична — координат точки нет, карту не рисуем (point=None).
    await botmod._send_report_prompt(_CaptureAPI(), report, None)
    kb = sent[-1][1]
    btns = [b["callback_data"] for row in kb["inline_keyboard"] for b in row]
    assert all(d != encode_payload(pid, ADD_MNO) for d in btns)
