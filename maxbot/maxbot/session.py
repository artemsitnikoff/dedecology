"""Стейт-машина интерактивного приёма МНО в личке Макс-бота.

ЧИСТАЯ логика БЕЗ импорта maxapi — юнит-тестируется оффлайн (см.
`maxbot/tests/test_session.py`). Обращение в личке создаётся ТОЛЬКО после
выбора площадки (кнопка МНО / «Нет в списке»), поэтому между `prepare` и
`finalize` нужно где-то держать: скачанные фото, разобранные поля адреса и
список кандидатов. Этим занимается `PendingReport` + `PendingStore`.

Хранилище — процессное (in-memory). Макс-бот запускается ОДНИМ long-polling
процессом (`maxbot/main.py` → `dp.start_polling`), поэтому единого стора
достаточно. При масштабировании на несколько воркеров понадобился бы Redis —
сейчас это осознанно не нужно.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

# TTL отложенного обращения: если пользователь не выбрал площадку за 30 минут,
# сессия истекает — фото/разбор выкидываются, повторный тап получает «истекла».
PENDING_TTL = 1800.0

# Префикс payload callback-кнопок. payload MAX ограничен 256 символами; наш
# формат «m:{uuid4-hex}:{idx}» ~36 символов — с большим запасом.
PAYLOAD_PREFIX = "m"

# Спец-индекс «без привязки к площадке» («Нет в списке» / «Отправить без привязки»).
NO_MNO = "x"

# Максимальная длина текста инлайн-кнопки (в MAX Button.text — 1..64 символа;
# держим короче для читаемости в узком столбце клавиатуры).
BUTTON_MAX = 40


def new_pending_id() -> str:
    """Сгенерировать id отложенного обращения (uuid4 hex — без двоеточий,
    чтобы не ломать разбор payload формата `m:{pid}:{idx}`)."""
    return uuid.uuid4().hex


def chat_key(chat_id, user_id) -> str:
    """Ключ диалога «chat_id:user_id» — стабилен между message_created
    (msg.recipient.chat_id / msg.sender.user_id) и message_callback
    (message.recipient.chat_id / callback.user.user_id)."""
    return f"{chat_id}:{user_id}"


def encode_payload(pending_id: str, idx) -> str:
    """Собрать payload кнопки: `m:{pending_id}:{idx}`. idx — int (индекс
    кандидата, 0-based) или строка `NO_MNO` («x»)."""
    return f"{PAYLOAD_PREFIX}:{pending_id}:{idx}"


def decode_payload(s: str) -> tuple[str, int | str] | None:
    """Разобрать payload кнопки. Вернуть (pending_id, idx) либо None, если
    формат чужой/битый. idx — int (>=0) или строка `NO_MNO`."""
    if not s:
        return None
    parts = s.split(":")
    if len(parts) != 3 or parts[0] != PAYLOAD_PREFIX:
        return None
    pid, raw = parts[1], parts[2]
    if not pid:
        return None
    if raw == NO_MNO:
        return pid, NO_MNO
    try:
        idx = int(raw)
    except ValueError:
        return None
    if idx < 0:
        return None
    return pid, idx


def _truncate(s: str, limit: int) -> str:
    s = (s or "").strip()
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 1)].rstrip() + "…"


def button_text(i: int, name: str, address: str = "") -> str:
    """Подпись кнопки кандидата: «i. Название — адрес», обрезанная до BUTTON_MAX."""
    name = (name or "").strip()
    address = (address or "").strip()
    label = name or "Без названия"
    if address:
        label = f"{label} — {address}"
    return _truncate(f"{i}. {label}", BUTTON_MAX)


def map_query(point, candidates) -> str:
    """Строка `pts` для рендера карты: «lat,lon;lat,lon;…» из координат
    кандидатов В ТОМ ЖЕ ПОРЯДКЕ, что и candidates. Кандидаты без координат
    пропускаются. `point` (точка обращения) в pts НЕ входит — она уходит в
    endpoint карты отдельными параметрами lat/lon; аргумент оставлен для
    симметрии вызова и явности (сколько точек рисуем)."""
    _ = point  # намеренно не используется (см. docstring)
    parts: list[str] = []
    for c in candidates or []:
        lat = c.get("lat")
        lon = c.get("lon")
        if lat is None or lon is None:
            continue
        parts.append(f"{lat},{lon}")
    return ";".join(parts)


def human_distance(distance_m) -> str:
    """«420 м» / «1.2 км» из метров; «» — если расстояние неизвестно/битое."""
    if distance_m is None:
        return ""
    try:
        m = float(distance_m)
    except (TypeError, ValueError):
        return ""
    if m < 1000:
        return f"{int(round(m))} м"
    return f"{m / 1000:.1f} км"


def merge_parsed(base: dict, override: dict) -> dict:
    """override поверх base, но ПУСТЫЕ значения override (None/"") не затирают
    base. Нужно при ответе-адресом: новый разбор даёт region/city/street, но не
    должен потерять исходные comment/photo_time из подписи к фото."""
    out = dict(base or {})
    for k, v in (override or {}).items():
        if v not in (None, ""):
            out[k] = v
    return out


@dataclass
class PendingReport:
    """Отложенное обращение из лички: всё, что нужно для finalize после выбора."""

    pending_id: str
    chat_id: int | None
    user_id: int | None
    photos: list[bytes] = field(default_factory=list)
    sender_name: str = ""
    msg_url: str = ""
    msg_id: str = ""
    parsed: dict = field(default_factory=dict)
    candidates: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    finalized: bool = False
    # Ждём от пользователя адрес текстом (координаты не распознались из подписи).
    awaiting_address: bool = False

    @property
    def key(self) -> str:
        return chat_key(self.chat_id, self.user_id)


class PendingStore:
    """Процессное хранилище отложенных обращений с TTL."""

    def __init__(self, ttl: float = PENDING_TTL):
        self._ttl = ttl
        self._items: dict[str, PendingReport] = {}

    def put(self, report: PendingReport) -> None:
        self._items[report.pending_id] = report

    def get(self, pending_id: str) -> PendingReport | None:
        return self._items.get(pending_id)

    def pop(self, pending_id: str) -> PendingReport | None:
        return self._items.pop(pending_id, None)

    def purge(self, now: float) -> int:
        """Удалить протухшие (старше TTL) записи. Вернуть их число."""
        expired = [
            pid for pid, r in self._items.items() if (now - r.created_at) > self._ttl
        ]
        for pid in expired:
            del self._items[pid]
        return len(expired)

    def find_awaiting(self, key: str, now: float | None = None) -> PendingReport | None:
        """Найти НЕ протухшее, не завершённое обращение этого чата, ожидающее
        адрес. При нескольких — вернуть самое свежее (latest created_at)."""
        best: PendingReport | None = None
        for r in self._items.values():
            if r.finalized or not r.awaiting_address:
                continue
            if r.key != key:
                continue
            if now is not None and (now - r.created_at) > self._ttl:
                continue
            if best is None or r.created_at > best.created_at:
                best = r
        return best

    def __len__(self) -> int:  # удобно в тестах/диагностике
        return len(self._items)
