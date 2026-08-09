"""Юнит-тесты тонкого Telegram Bot API клиента tgapi.py.

Чистые билдеры/парсеры — без сети. Сетевые методы — через httpx.MockTransport
(оффлайн, без реального api.telegram.org): проверяем реальные тела запросов,
разбор {ok,result}, скачивание фото (getFile → download) и потолок размера.
"""

from __future__ import annotations

import json

import httpx
import pytest

from telegrambot.tgapi import (
    TelegramAPI,
    display_name,
    extract_location,
    inline_keyboard,
    largest_photo_file_id,
    message_text,
    remove_reply_keyboard,
    reply_keyboard_location,
    update_kind,
)


# ---------------------------------------------------------------------------
# Чистые билдеры разметки.
# ---------------------------------------------------------------------------


def test_inline_keyboard_shape_and_drops_empty_rows():
    kb = inline_keyboard([[("A", "m:1:0")], [("B", "m:1:x")], []])
    assert kb == {
        "inline_keyboard": [
            [{"text": "A", "callback_data": "m:1:0"}],
            [{"text": "B", "callback_data": "m:1:x"}],
        ]
    }


def test_reply_keyboard_location_has_request_location():
    kb = reply_keyboard_location("📍 Отправить геопозицию")
    btn = kb["keyboard"][0][0]
    assert btn["text"] == "📍 Отправить геопозицию"
    assert btn["request_location"] is True
    assert kb["resize_keyboard"] is True
    assert kb["one_time_keyboard"] is True


def test_remove_reply_keyboard():
    assert remove_reply_keyboard() == {"remove_keyboard": True}


# ---------------------------------------------------------------------------
# Чистый разбор апдейтов.
# ---------------------------------------------------------------------------


def test_update_kind():
    assert update_kind({"update_id": 1, "message": {"text": "hi"}}) == "message"
    assert update_kind({"update_id": 2, "callback_query": {"id": "x"}}) == "callback_query"
    # callback_query имеет приоритет, если вдруг оба (на практике не бывает)
    assert update_kind({"callback_query": {"id": "x"}, "message": {}}) == "callback_query"
    assert update_kind({"update_id": 3, "edited_message": {}}) is None
    assert update_kind({}) is None
    assert update_kind(None) is None  # type: ignore[arg-type]


def test_largest_photo_file_id_picks_last():
    msg = {
        "photo": [
            {"file_id": "small", "width": 90},
            {"file_id": "mid", "width": 320},
            {"file_id": "big", "width": 1280},
        ]
    }
    assert largest_photo_file_id(msg) == "big"


def test_largest_photo_file_id_none_when_no_photo():
    assert largest_photo_file_id({"text": "no photo"}) is None
    assert largest_photo_file_id({"photo": []}) is None
    assert largest_photo_file_id({"photo": [{"width": 1}]}) is None  # нет file_id


def test_extract_location():
    assert extract_location({"location": {"latitude": 55.75, "longitude": 37.61}}) == (55.75, 37.61)
    assert extract_location({"text": "no loc"}) is None
    assert extract_location({"location": {"latitude": None, "longitude": 1.0}}) is None
    assert extract_location({"location": {"latitude": "x", "longitude": "y"}}) is None


def test_message_text_prefers_text_then_caption():
    assert message_text({"text": "  привет "}) == "привет"
    assert message_text({"caption": " подпись "}) == "подпись"
    assert message_text({"photo": [{"file_id": "b"}]}) == ""


def test_display_name():
    assert display_name({"first_name": "Иван", "last_name": "Петров"}) == "Иван Петров"
    assert display_name({"first_name": "Иван"}) == "Иван"
    assert display_name({"username": "eco_user"}) == "@eco_user"
    assert display_name({"id": 777}) == "777"
    assert display_name(None) == ""


# ---------------------------------------------------------------------------
# Сетевые методы через MockTransport.
# ---------------------------------------------------------------------------


def _method_of(request: httpx.Request) -> str:
    return request.url.path.rsplit("/", 1)[-1]


def _make_api(captured: list, *, ok: bool = True, result=None, file_content: bytes = b"JPEGDATA"):
    """TelegramAPI с MockTransport: складывает запросы в captured, отдаёт заготовленные ответы."""

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        path = request.url.path
        if "/file/bot" in path:  # скачивание файла (не метод API)
            return httpx.Response(200, content=file_content)
        method = _method_of(request)
        if not ok:
            return httpx.Response(200, json={"ok": False, "description": "bad request"})
        if method == "getFile":
            return httpx.Response(
                200, json={"ok": True, "result": {"file_id": "F", "file_path": "photos/file_1.jpg"}}
            )
        if method == "getUpdates":
            return httpx.Response(
                200,
                json={"ok": True, "result": [{"update_id": 10, "message": {"text": "hi"}}]},
            )
        payload = result if result is not None else {"message_id": 42}
        return httpx.Response(200, json={"ok": True, "result": payload})

    return TelegramAPI("TESTTOKEN", transport=httpx.MockTransport(handler))


async def test_send_message_posts_json_and_returns_result():
    captured: list = []
    api = _make_api(captured)
    res = await api.send_message(
        123, "привет", reply_markup=inline_keyboard([[("A", "m:1:0")]])
    )
    assert res == {"message_id": 42}
    req = captured[-1]
    assert _method_of(req) == "sendMessage"
    body = json.loads(req.content)
    assert body["chat_id"] == 123
    assert body["text"] == "привет"
    assert body["parse_mode"] == "HTML"
    # reply_markup в JSON-теле остаётся вложенным объектом
    assert body["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "m:1:0"


async def test_call_returns_none_on_not_ok():
    captured: list = []
    api = _make_api(captured, ok=False)
    assert await api.send_message(1, "x") is None


async def test_answer_callback_query_body():
    captured: list = []
    api = _make_api(captured)
    await api.answer_callback_query("CBID", "Принято ✅")
    req = captured[-1]
    assert _method_of(req) == "answerCallbackQuery"
    body = json.loads(req.content)
    assert body["callback_query_id"] == "CBID"
    assert body["text"] == "Принято ✅"


async def test_delete_message_body():
    captured: list = []
    api = _make_api(captured)
    await api.delete_message(55, 900)
    req = captured[-1]
    assert _method_of(req) == "deleteMessage"
    body = json.loads(req.content)
    assert body == {"chat_id": 55, "message_id": 900}


async def test_send_photo_multipart_serializes_reply_markup():
    captured: list = []
    api = _make_api(captured, result={"message_id": 7})
    res = await api.send_photo(
        9, b"BINARYIMG", caption="карта", reply_markup=inline_keyboard([[("A", "m:1:0")]])
    )
    assert res == {"message_id": 7}
    req = captured[-1]
    assert _method_of(req) == "sendPhoto"
    content = req.content  # multipart/form-data
    assert b"BINARYIMG" in content
    # reply_markup в multipart обязан быть JSON-СТРОКОЙ, а не вложенным объектом.
    assert b"reply_markup" in content
    assert b"inline_keyboard" in content
    assert b'"callback_data": "m:1:0"' in content or b'"callback_data":"m:1:0"' in content


async def test_download_by_file_id_getfile_then_download():
    captured: list = []
    api = _make_api(captured, file_content=b"PHOTOBYTES")
    data = await api.download_by_file_id("F", max_bytes=10_000)
    assert data == b"PHOTOBYTES"
    paths = [r.url.path for r in captured]
    assert any(p.endswith("/getFile") for p in paths)
    assert any("/file/bot" in p for p in paths)
    # порядок: сначала getFile, затем скачивание файла
    assert paths[0].endswith("/getFile")
    assert "/file/bot" in paths[1]


async def test_download_respects_max_bytes():
    captured: list = []
    api = _make_api(captured, file_content=b"X" * 100)
    # потолок 10 байт < 100 байт контента → None
    assert await api.download_by_file_id("F", max_bytes=10) is None


async def test_download_by_file_id_none_when_getfile_fails():
    captured: list = []
    api = _make_api(captured, ok=False)
    assert await api.download_by_file_id("F", max_bytes=10_000) is None


async def test_get_updates_returns_list_and_body():
    captured: list = []
    api = _make_api(captured)
    updates = await api.get_updates(offset=5, timeout=0)
    assert isinstance(updates, list)
    assert updates[0]["update_id"] == 10
    req = captured[-1]
    assert _method_of(req) == "getUpdates"
    body = json.loads(req.content)
    assert body["offset"] == 5
    assert body["allowed_updates"] == ["message", "callback_query"]


async def test_get_updates_raises_on_not_ok():
    captured: list = []
    api = _make_api(captured, ok=False)
    with pytest.raises(httpx.HTTPError):
        await api.get_updates(offset=0, timeout=0)
