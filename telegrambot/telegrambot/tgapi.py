"""Тонкий клиент Telegram Bot API поверх httpx — ЕДИНСТВЕННЫЙ источник Telegram-специфики.

БЕЗ python-telegram-bot: сырые HTTP-вызовы к https://api.telegram.org/bot<token>/<method>
(long-polling getUpdates) + скачивание файлов с https://api.telegram.org/file/bot<token>/<path>.
parse_mode по умолчанию — HTML.

Дизайн устойчивости (по стилю maxbot):
  * каждый исходящий вызов (send_*/edit/delete/answer/action) — best-effort: сеть/не-ok
    логируются и возвращают None, обработчик не падает;
  * get_updates при сбое поднимает httpx-ошибку — верхний цикл main.py делает backoff;
  * download_file — потоковое скачивание с потолком размера (→ None при превышении/ошибке).

Клиент stateless по HTTP: под каждый вызов открывается httpx.AsyncClient (можно
подменить transport в тестах через конструктор — так гоняем оффлайн-юниты на MockTransport).

Здесь же — ЧИСТЫЕ (без сети) хелперы:
  * билдеры разметки: inline_keyboard / reply_keyboard_location / remove_reply_keyboard;
  * разбор апдейтов: update_kind / largest_photo_file_id / extract_location /
    message_text / display_name — покрыты юнит-тестами.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("dedecology.telegrambot")

_API_ROOT = "https://api.telegram.org"

# Обычные вызовы API (send/edit/delete/answer/action/getFile) — короткий таймаут.
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)

# Скачивание файла (фото) — потоково, чуть длиннее.
_FILE_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Длина long-poll getUpdates по умолчанию (сек). Таймаут httpx на чтение обязан
# быть ЗАМЕТНО больше, иначе клиент рвёт соединение раньше сервера Telegram.
DEFAULT_POLL_TIMEOUT = 25


# ---------------------------------------------------------------------------
# Чистые билдеры разметки (без сети) — тестируются отдельно.
# ---------------------------------------------------------------------------

def inline_keyboard(rows: list[list[tuple[str, str]]]) -> dict:
    """InlineKeyboardMarkup из рядов кнопок (text, callback_data).

    Пустые ряды отфильтровываются. callback_data Telegram ограничен 64 БАЙТАМИ —
    наши payload (m:/t:/s:) в лимит влезают (см. session.py)."""
    keyboard = [
        [{"text": text, "callback_data": data} for text, data in row]
        for row in rows
        if row
    ]
    return {"inline_keyboard": keyboard}


def reply_keyboard_location(
    button_text: str, *, resize: bool = True, one_time: bool = True
) -> dict:
    """ReplyKeyboardMarkup с единственной кнопкой запроса геопозиции
    (KeyboardButton request_location=True). Работает ТОЛЬКО в личке."""
    return {
        "keyboard": [[{"text": button_text, "request_location": True}]],
        "resize_keyboard": resize,
        "one_time_keyboard": one_time,
    }


def remove_reply_keyboard() -> dict:
    """ReplyKeyboardRemove — убрать reply-клавиатуру (гео-кнопку) у пользователя."""
    return {"remove_keyboard": True}


# ---------------------------------------------------------------------------
# Чистый разбор апдейтов (без сети) — тестируется отдельно.
# ---------------------------------------------------------------------------

def update_kind(update: dict) -> str | None:
    """Тип апдейта, который мы обрабатываем: 'message' | 'callback_query' | None."""
    if not isinstance(update, dict):
        return None
    if isinstance(update.get("callback_query"), dict):
        return "callback_query"
    if isinstance(update.get("message"), dict):
        return "message"
    return None


def largest_photo_file_id(message: dict) -> str | None:
    """file_id САМОГО КРУПНОГО размера фото сообщения (photo[-1].file_id) либо None.

    В Telegram поле `photo` — массив PhotoSize одного и того же снимка в разных
    разрешениях, по возрастанию; последний элемент — максимальное качество."""
    photos = message.get("photo") if isinstance(message, dict) else None
    if not isinstance(photos, list) or not photos:
        return None
    last = photos[-1]
    if not isinstance(last, dict):
        return None
    fid = last.get("file_id")
    return str(fid) if fid else None


def extract_location(message: dict) -> tuple[float, float] | None:
    """(lat, lon) из message.location либо None. Мусор (нечисловые) → None."""
    loc = message.get("location") if isinstance(message, dict) else None
    if not isinstance(loc, dict):
        return None
    lat, lon = loc.get("latitude"), loc.get("longitude")
    if lat is None or lon is None:
        return None
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def message_text(message: dict) -> str:
    """Текст сообщения: message.text ИЛИ подпись к фото message.caption (что есть)."""
    if not isinstance(message, dict):
        return ""
    return ((message.get("text") or message.get("caption")) or "").strip()


def display_name(from_user: dict | None) -> str:
    """«Имя Фамилия» / @username / str(id) из объекта Telegram User (message.from)."""
    if not isinstance(from_user, dict):
        return ""
    first = str(from_user.get("first_name") or "").strip()
    last = str(from_user.get("last_name") or "").strip()
    full = f"{first} {last}".strip()
    if full:
        return full
    username = str(from_user.get("username") or "").strip()
    if username:
        return f"@{username}"
    uid = from_user.get("id")
    return str(uid) if uid is not None else ""


# ---------------------------------------------------------------------------
# HTTP-клиент Telegram Bot API.
# ---------------------------------------------------------------------------

class TelegramAPI:
    """Асинхронный клиент Telegram Bot API. token — из @BotFather.

    :param transport: опциональный httpx-транспорт (для тестов подставляем
        httpx.MockTransport, гоняем оффлайн без сети)."""

    def __init__(self, token: str, *, transport: httpx.AsyncBaseTransport | None = None):
        self._token = token
        self._api_base = f"{_API_ROOT}/bot{token}"
        self._file_base = f"{_API_ROOT}/file/bot{token}"
        self._transport = transport

    # -- низкоуровневый вызов метода API -----------------------------------

    async def _call(
        self,
        method: str,
        *,
        json: dict | None = None,
        data: dict | None = None,
        files: list | None = None,
        timeout: httpx.Timeout = _TIMEOUT,
    ) -> dict | None:
        """POST на /<method>; вернуть result из {ok,result} либо None при ошибке/не-ok.

        Best-effort: сетевые сбои и Telegram-ответ ok=false логируются и дают None —
        обработчики не должны падать из-за неудачной отправки тоста/правки."""
        url = f"{self._api_base}/{method}"
        # reply_markup в multipart обязан быть JSON-строкой (не вложенным объектом).
        if data is not None and isinstance(data.get("reply_markup"), (dict, list)):
            import json as _json

            data = {**data, "reply_markup": _json.dumps(data["reply_markup"], ensure_ascii=False)}
        try:
            async with httpx.AsyncClient(
                timeout=timeout, transport=self._transport
            ) as client:
                resp = await client.post(url, json=json, data=data, files=files)
        except httpx.HTTPError as exc:
            logger.warning("telegram %s failed (network): %s", method, exc)
            return None
        try:
            payload = resp.json()
        except ValueError:
            logger.warning("telegram %s non-JSON (status %s): %s", method, resp.status_code, resp.text[:300])
            return None
        if not isinstance(payload, dict) or not payload.get("ok"):
            logger.warning(
                "telegram %s not ok (status %s): %s",
                method,
                resp.status_code,
                (payload.get("description") if isinstance(payload, dict) else payload),
            )
            return None
        return payload.get("result")

    # -- getUpdates (long-poll) --------------------------------------------

    async def get_updates(self, offset: int, timeout: int = DEFAULT_POLL_TIMEOUT) -> list[dict]:
        """Long-poll очередной пачки апдейтов. Поднимает httpx-ошибку при сбое сети/не-ok
        (верхний цикл делает backoff). allowed_updates ограничивает поток нужными типами."""
        url = f"{self._api_base}/getUpdates"
        body = {
            "offset": offset,
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }
        # Read-таймаут = длина поллинга + запас (иначе клиент рвёт соединение раньше сервера).
        read_timeout = httpx.Timeout(timeout + 10.0, connect=10.0)
        async with httpx.AsyncClient(timeout=read_timeout, transport=self._transport) as client:
            resp = await client.post(url, json=body)
        # Санитизируем ошибку статуса: httpx кладёт в сообщение URL с ТОКЕНОМ
        # (…/bot<token>/getUpdates), а верхний цикл логирует её через logger.exception →
        # токен утёк бы в лог/трейсбек. Поднимаем чистую ошибку без URL (`from None` — не
        # тащим исходное исключение с токеном в __context__/__cause__).
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            raise httpx.HTTPError(f"getUpdates HTTP {resp.status_code}") from None
        payload = resp.json()
        if not isinstance(payload, dict) or not payload.get("ok"):
            raise httpx.HTTPError(
                f"getUpdates not ok: {payload.get('description') if isinstance(payload, dict) else payload}"
            )
        result = payload.get("result")
        return result if isinstance(result, list) else []

    # -- отправка сообщений / действий -------------------------------------

    async def send_message(
        self,
        chat_id,
        text: str,
        *,
        parse_mode: str | None = "HTML",
        reply_markup: dict | None = None,
        disable_web_page_preview: bool = True,
    ) -> dict | None:
        """sendMessage. Возвращает объект отправленного сообщения (для message_id) либо None."""
        body: dict = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if parse_mode:
            body["parse_mode"] = parse_mode
        if reply_markup is not None:
            body["reply_markup"] = reply_markup
        return await self._call("sendMessage", json=body)

    async def send_photo(
        self,
        chat_id,
        photo: bytes,
        *,
        caption: str | None = None,
        filename: str = "photo.jpg",
        parse_mode: str | None = "HTML",
        reply_markup: dict | None = None,
    ) -> dict | None:
        """sendPhoto (multipart, байты фото). Возвращает объект сообщения либо None."""
        data: dict = {"chat_id": str(chat_id)}
        if caption is not None:
            data["caption"] = caption
            if parse_mode:
                data["parse_mode"] = parse_mode
        if reply_markup is not None:
            data["reply_markup"] = reply_markup
        files = [("photo", (filename, photo, "image/jpeg"))]
        return await self._call("sendPhoto", data=data, files=files, timeout=_FILE_TIMEOUT)

    async def send_chat_action(self, chat_id, action: str) -> dict | None:
        """sendChatAction (напр. 'upload_photo' — индикатор «отправляет фото»)."""
        return await self._call("sendChatAction", json={"chat_id": chat_id, "action": action})

    async def answer_callback_query(
        self, callback_query_id: str, text: str | None = None, *, show_alert: bool = False
    ) -> dict | None:
        """answerCallbackQuery — тост над кнопкой (мгновенная обратная связь на тап)."""
        body: dict = {"callback_query_id": callback_query_id}
        if text is not None:
            body["text"] = text
        if show_alert:
            body["show_alert"] = True
        return await self._call("answerCallbackQuery", json=body)

    async def edit_message_reply_markup(
        self, chat_id, message_id, reply_markup: dict | None = None
    ) -> dict | None:
        """editMessageReplyMarkup — заменить/снять инлайн-клавиатуру у сообщения."""
        body: dict = {"chat_id": chat_id, "message_id": message_id}
        if reply_markup is not None:
            body["reply_markup"] = reply_markup
        return await self._call("editMessageReplyMarkup", json=body)

    async def delete_message(self, chat_id, message_id) -> dict | None:
        """deleteMessage — убрать сообщение с кнопками (быстрее правки) или карту."""
        return await self._call("deleteMessage", json={"chat_id": chat_id, "message_id": message_id})

    async def delete_webhook(self, *, drop_pending_updates: bool = False) -> dict | None:
        """deleteWebhook — снять вебхук перед long-polling (иначе getUpdates 409)."""
        return await self._call(
            "deleteWebhook", json={"drop_pending_updates": drop_pending_updates}
        )

    # -- скачивание файла (фото) -------------------------------------------

    async def get_file(self, file_id: str) -> dict | None:
        """getFile → объект File c file_path (для сборки URL скачивания) либо None."""
        return await self._call("getFile", json={"file_id": file_id})

    async def download_file(self, file_path: str, *, max_bytes: int) -> bytes | None:
        """Скачать файл по file_path (из getFile). Потоково с потолком max_bytes.

        URL: https://api.telegram.org/file/bot<token>/<file_path>. На любую
        ошибку/превышение размера → None."""
        if not file_path:
            return None
        url = f"{self._file_base}/{file_path}"
        try:
            async with httpx.AsyncClient(
                timeout=_FILE_TIMEOUT, transport=self._transport, follow_redirects=True
            ) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            logger.warning(
                                "download_file too large (> %d bytes) path=%s", max_bytes, file_path
                            )
                            return None
                        chunks.append(chunk)
        except httpx.HTTPError as exc:
            # НЕ логируем сам exc: httpx кладёт в него URL с токеном (…/file/bot<token>/…).
            logger.warning("download_file failed path=%s: %s", file_path, type(exc).__name__)
            return None
        return b"".join(chunks)

    async def download_by_file_id(self, file_id: str, *, max_bytes: int) -> bytes | None:
        """Удобная связка getFile → download_file: file_id → байты фото (или None)."""
        info = await self.get_file(file_id)
        if not isinstance(info, dict):
            return None
        file_path = info.get("file_path")
        if not file_path:
            logger.warning("get_file returned no file_path for file_id=%s", file_id)
            return None
        return await self.download_file(str(file_path), max_bytes=max_bytes)
