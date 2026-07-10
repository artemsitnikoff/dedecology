"""Юнит-тесты чистой логики session.py (БЕЗ импорта maxapi).

Покрывают контракт: payload roundtrip, TTL-purge, обрезку кнопок, map_query,
merge_parsed и find_awaiting.
"""

from __future__ import annotations

from maxbot.session import (
    BUTTON_MAX,
    NO_MNO,
    PENDING_TTL,
    PendingReport,
    PendingStore,
    button_text,
    chat_key,
    decode_payload,
    decode_subtype_payload,
    decode_type_payload,
    encode_payload,
    encode_subtype_payload,
    encode_type_payload,
    human_distance,
    map_query,
    merge_parsed,
    new_pending_id,
)


# --- payload encode/decode ------------------------------------------------


def test_payload_roundtrip_int():
    pid = new_pending_id()
    assert decode_payload(encode_payload(pid, 0)) == (pid, 0)
    assert decode_payload(encode_payload(pid, 4)) == (pid, 4)


def test_payload_roundtrip_no_mno():
    pid = new_pending_id()
    payload = encode_payload(pid, NO_MNO)
    assert payload == f"m:{pid}:x"
    assert decode_payload(payload) == (pid, NO_MNO)


def test_new_pending_id_has_no_colon():
    # id не должен содержать ':' — иначе разбор payload из 3 частей сломается.
    assert ":" not in new_pending_id()


def test_payload_stays_short():
    # payload MAX ограничен 256 символами.
    assert len(encode_payload(new_pending_id(), 5)) < 256


def test_decode_payload_rejects_garbage():
    assert decode_payload("") is None
    assert decode_payload(None) is None  # type: ignore[arg-type]
    assert decode_payload("x:y") is None  # не 3 части
    assert decode_payload("z:pid:0") is None  # чужой префикс
    assert decode_payload("m::0") is None  # пустой pid
    assert decode_payload("m:pid:abc") is None  # idx не int и не 'x'
    assert decode_payload("m:pid:-1") is None  # отрицательный индекс


# --- type payload (шаг 2: выбор типа инцидента) ----------------------------


def test_type_payload_roundtrip():
    p = encode_type_payload("abc123", "fire")
    assert decode_type_payload(p) == ("abc123", "fire")


def test_type_payload_empty_code_is_skip():
    p = encode_type_payload("abc123", "")
    assert decode_type_payload(p) == ("abc123", "")


def test_decode_type_payload_rejects_foreign():
    assert decode_type_payload("m:abc:0") is None  # это МНО-payload, не типовой
    assert decode_type_payload("garbage") is None
    assert decode_type_payload("") is None


def test_mno_and_type_payloads_do_not_collide():
    # decode_payload не принимает типовой payload и наоборот
    assert decode_payload(encode_type_payload("p", "fire")) is None
    assert decode_type_payload(encode_payload("p", 0)) is None


# --- subtype payload (шаг 3: подтип для типа «Отсутствует доступ к МНО») -------


def test_subtype_payload_roundtrip():
    p = encode_subtype_payload("abc123", "blocked_by_car")
    assert decode_subtype_payload(p) == ("abc123", "blocked_by_car")


def test_subtype_payload_requires_code():
    # Подтип обязателен — пустой код отвергается (в отличие от типа с «Пропустить»).
    assert decode_subtype_payload("s:abc123:") is None


def test_subtype_payload_isolated_from_type_and_mno():
    p = encode_subtype_payload("p", "other_reason")
    assert decode_type_payload(p) is None  # префикс s != t
    assert decode_payload(p) is None  # префикс s != m
    assert decode_subtype_payload(encode_type_payload("p", "fire")) is None
    assert decode_subtype_payload("garbage") is None
    assert decode_subtype_payload("") is None


# --- button_text truncation ----------------------------------------------


def test_button_text_prefers_reg():
    # реестровый № приоритетнее названия
    assert button_text(1, "78-06-002210", "МНО-1") == "1. 78-06-002210"


def test_button_text_name_when_no_reg():
    assert button_text(1, "", "МНО-1") == "1. МНО-1"


def test_button_text_truncated():
    long_reg = "Очень длинное название площадки накопления твёрдых коммунальных отходов"
    txt = button_text(2, long_reg)
    assert len(txt) <= BUTTON_MAX
    assert txt.endswith("…")
    assert txt.startswith("2. ")


def test_button_text_no_name_fallback():
    assert button_text(3, "", "") == "3. Без названия"


# --- map_query ------------------------------------------------------------


def test_map_query_orders_and_joins():
    cands = [
        {"lat": 55.70, "lon": 37.60},
        {"lat": 55.71, "lon": 37.61},
    ]
    assert map_query((55.5, 37.5), cands) == "55.7,37.6;55.71,37.61"


def test_map_query_skips_missing_coords():
    cands = [
        {"lat": 55.70, "lon": 37.60},
        {"lat": None, "lon": 37.61},  # пропускается
        {"name": "нет координат"},  # пропускается
    ]
    assert map_query(None, cands) == "55.7,37.6"


def test_map_query_empty():
    assert map_query(None, []) == ""


# --- human_distance -------------------------------------------------------


def test_human_distance():
    assert human_distance(420) == "420 м"
    assert human_distance(1250) == "1.2 км"
    assert human_distance(None) == ""
    assert human_distance("nope") == ""


# --- merge_parsed ---------------------------------------------------------


def test_merge_parsed_keeps_original_on_empty_override():
    base = {"region": "Москва", "comment": "Радар №7", "coords": ""}
    override = {"region": "Московская область", "comment": "", "coords": "55.7,37.6"}
    out = merge_parsed(base, override)
    assert out["region"] == "Московская область"  # непустой override победил
    assert out["comment"] == "Радар №7"  # пустой override НЕ затёр исходное
    assert out["coords"] == "55.7,37.6"


# --- chat_key -------------------------------------------------------------


def test_chat_key():
    assert chat_key(10, 20) == "10:20"


# --- PendingStore TTL / find_awaiting ------------------------------------


def _report(pid: str, *, created_at: float, awaiting: bool = False, chat=1, user=2):
    return PendingReport(
        pending_id=pid,
        chat_id=chat,
        user_id=user,
        created_at=created_at,
        awaiting_address=awaiting,
    )


def test_store_put_get_pop():
    store = PendingStore()
    r = _report("a", created_at=100.0)
    store.put(r)
    assert store.get("a") is r
    assert store.pop("a") is r
    assert store.get("a") is None
    assert store.pop("missing") is None


def test_store_purge_removes_expired():
    store = PendingStore(ttl=PENDING_TTL)
    now = 10_000.0
    fresh = _report("fresh", created_at=now - 10)  # 10 с назад — живой
    old = _report("old", created_at=now - PENDING_TTL - 1)  # старше TTL — протух
    store.put(fresh)
    store.put(old)
    removed = store.purge(now)
    assert removed == 1
    assert store.get("fresh") is fresh
    assert store.get("old") is None


def test_find_awaiting_returns_latest_non_expired():
    store = PendingStore(ttl=PENDING_TTL)
    now = 10_000.0
    key = chat_key(1, 2)
    older = _report("o", created_at=now - 100, awaiting=True)
    newer = _report("n", created_at=now - 10, awaiting=True)
    not_awaiting = _report("x", created_at=now - 5, awaiting=False)
    other_chat = _report("z", created_at=now - 1, awaiting=True, chat=9, user=9)
    for r in (older, newer, not_awaiting, other_chat):
        store.put(r)
    found = store.find_awaiting(key, now=now)
    assert found is newer  # самое свежее ожидающее для этого чата


def test_find_awaiting_skips_expired():
    store = PendingStore(ttl=PENDING_TTL)
    now = 10_000.0
    key = chat_key(1, 2)
    expired = _report("e", created_at=now - PENDING_TTL - 1, awaiting=True)
    store.put(expired)
    assert store.find_awaiting(key, now=now) is None


def test_find_awaiting_none_when_finalized():
    store = PendingStore()
    r = _report("a", created_at=100.0, awaiting=True)
    r.finalized = True
    store.put(r)
    assert store.find_awaiting(chat_key(1, 2), now=100.0) is None
