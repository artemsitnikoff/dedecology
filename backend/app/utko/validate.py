"""Ручная валидация входящих тел УТКО-эндпоинтов по таблицам проверок доки.

Почему вручную, а не Pydantic: авто-422 FastAPI перехватывается глобальным хэндлером
приложения (конверт {error:{...}}), и тексты разошлись бы с таблицами доки. Здесь каждая
проверка кидает `UtkoError` с ДОСЛОВНЫМ текстом и кодом из таблиц.

Порядок проверок для каждого элемента строго по таблицам:
  1) наличие обязательных атрибутов → «Отсутствует обязательный атрибут <имя>» (422)
  2) соответствие типа данных      → «Неверный тип данных у атрибута <имя>» (422)
  3+) доменные проверки (существование eventId/mnoId, значения по справочникам).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from . import dicts, errors

_MISSING = object()

# Потолок размера страницы query: take<=0 или больше этого → MAX_TAKE (защита от
# безлимитного ответа; клиент добирает остальное пагинацией skip/take, полный объём виден
# в count ответа). Совпадает с рекомендацией доки «take не более 1000».
MAX_TAKE = 1000
# Разумный потолок длины произвольной клиентской строки externalEventId.
_EXTERNAL_EVENT_ID_MAX_LEN = 255


def require_list(body) -> list:
    """Тело должно быть JSON-массивом (confirm/video-events принимают массив)."""
    if not isinstance(body, list):
        raise errors.wrong_type("body")
    return body


def _parse_uuid(name: str, value) -> UUID:
    """value → UUID. Не строка / не UUID-формат → «Неверный тип данных у атрибута <name>»."""
    if not isinstance(value, str):
        raise errors.wrong_type(name)
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise errors.wrong_type(name)


def _parse_datetime_tz(name: str, value) -> datetime:
    """value → aware datetime (ISO-8601 с таймзоной). Иначе «Неверный тип данных …»."""
    if not isinstance(value, str):
        raise errors.wrong_type(name)
    raw = value.strip()
    # Поддержать суффикс «Z» (datetime.fromisoformat до 3.11 его не понимал).
    if raw.endswith("Z") or raw.endswith("z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        raise errors.wrong_type(name)
    if dt.tzinfo is None:
        # Тип требует «дата и время с указанием таймзоны».
        raise errors.wrong_type(name)
    return dt


def _require_int(name: str, value) -> int:
    """Целое число (не bool). Иначе «Неверный тип данных у атрибута <name>»."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise errors.wrong_type(name)
    return value


def _require_bool(name: str, value) -> bool:
    if not isinstance(value, bool):
        raise errors.wrong_type(name)
    return value


def _validate_events(raw_events, *, video: bool) -> list[dict]:
    """Проверить массив events: eventType (обяз, int, по справочнику) + typeContainer (опц).

    video=True → справочник ВИДЕО (вкл. 98, 99); иначе справочник ФОТО (confirm).
    Пустой массив допустим («нет нарушений»).
    """
    if raw_events is _MISSING or raw_events is None:
        return []
    if not isinstance(raw_events, list):
        raise errors.wrong_type("events")

    result: list[dict] = []
    for item in raw_events:
        if not isinstance(item, dict):
            raise errors.wrong_type("events")
        # eventType — обязателен.
        if "eventType" not in item:
            raise errors.missing_attr("eventType")
        event_type = _require_int("eventType", item["eventType"])
        valid = (
            dicts.is_valid_event_type_video(event_type)
            if video
            else dicts.is_valid_event_type_photo(event_type)
        )
        if not valid:
            raise errors.bad_value("eventType")
        entry: dict = {"eventType": event_type}
        # typeContainer — необязателен; если есть — int и по справочнику.
        if "typeContainer" in item and item["typeContainer"] is not None:
            type_container = _require_int("typeContainer", item["typeContainer"])
            if not dicts.is_valid_type_container(type_container):
                raise errors.bad_value("typeContainer")
            entry["typeContainer"] = type_container
        result.append(entry)
    return result


# --- confirm (truck-visit-events/confirm) ----------------------------------------


def validate_confirm_item(item) -> dict:
    """Проверить один элемент подтверждения (Таблица 1/2). Вернуть нормализованный dict.

    Проверка существования eventId в БД — ОТДЕЛЬНО (нужна сессия), см. роутер/сервис.
    """
    if not isinstance(item, dict):
        raise errors.wrong_type("eventId")

    # 1) обязательные атрибуты.
    if "eventId" not in item:
        raise errors.missing_attr("eventId")
    if "isEmptyConfirmed" not in item:
        raise errors.missing_attr("isEmptyConfirmed")

    # 2) типы.
    event_id = _parse_uuid("eventId", item["eventId"])
    is_empty_confirmed = _require_bool("isEmptyConfirmed", item["isEmptyConfirmed"])

    problem = item.get("problem")
    if problem is not None and not isinstance(problem, str):
        raise errors.wrong_type("problem")

    events = _validate_events(item.get("events", _MISSING), video=False)

    return {
        "event_id": event_id,
        "is_empty_confirmed": is_empty_confirmed,
        "problem": problem,
        "events": events,
    }


# --- video-events ----------------------------------------------------------------


def validate_video_item(item) -> dict:
    """Проверить один элемент видеопотока (Таблица 1/3). Вернуть нормализованный dict.

    Проверка существования mnoId в БД — ОТДЕЛЬНО (нужна сессия), см. роутер/сервис.
    """
    if not isinstance(item, dict):
        raise errors.wrong_type("mnoId")

    # 1) обязательные атрибуты.
    if "mnoId" not in item:
        raise errors.missing_attr("mnoId")
    if "eventTime" not in item:
        raise errors.missing_attr("eventTime")

    # 2) типы.
    mno_id = _parse_uuid("mnoId", item["mnoId"])
    event_time = _parse_datetime_tz("eventTime", item["eventTime"])

    external_event_id_raw = item.get("externalEventId")
    external_event_id = None
    if external_event_id_raw is not None:
        # Таблица ответа — «строка», пример echo-ит «123» (не UUID). Принимаем ЛЮБУЮ строку
        # (bounded), храним и возвращаем verbatim; не-строка → «Неверный тип данных …».
        if not isinstance(external_event_id_raw, str):
            raise errors.wrong_type("externalEventId")
        if len(external_event_id_raw) > _EXTERNAL_EVENT_ID_MAX_LEN:
            raise errors.wrong_type("externalEventId")
        external_event_id = external_event_id_raw

    photo_link = item.get("photoLink")
    if photo_link is not None:
        if not isinstance(photo_link, str):
            raise errors.wrong_type("photoLink")
        if len(photo_link) > 2083:
            raise errors.wrong_type("photoLink")

    events = _validate_events(item.get("events", _MISSING), video=True)

    return {
        "mno_id": mno_id,
        "external_event_id": external_event_id,
        "event_time": event_time,
        "photo_link": photo_link,
        "events": events,
    }


# --- query (truck-visit-events/query) --------------------------------------------


def validate_query(body) -> dict:
    """Проверить тело query: filter.fromDate (обяз, ISO с tz), toDate (опц), take/skip."""
    if not isinstance(body, dict):
        raise errors.wrong_type("body")

    filt = body.get("filter")
    if filt is None:
        raise errors.missing_attr("filter")
    if not isinstance(filt, dict):
        raise errors.wrong_type("filter")

    if "fromDate" not in filt or filt.get("fromDate") is None:
        raise errors.missing_attr("fromDate")
    from_date = _parse_datetime_tz("fromDate", filt["fromDate"])

    to_date = None
    if filt.get("toDate") is not None:
        to_date = _parse_datetime_tz("toDate", filt["toDate"])

    take = body.get("take", 0)
    take = _require_int("take", take)
    # Защита от безлимитного ответа: take<=0 (в т.ч. значение по умолчанию) или больше
    # потолка → MAX_TAKE. Клиент добирает остальное пагинацией skip/take; count в ответе
    # показывает полный объём под фильтр.
    if take <= 0 or take > MAX_TAKE:
        take = MAX_TAKE
    skip = body.get("skip", 0)
    skip = _require_int("skip", skip)
    if skip < 0:
        skip = 0

    return {"from_date": from_date, "to_date": to_date, "take": take, "skip": skip}
