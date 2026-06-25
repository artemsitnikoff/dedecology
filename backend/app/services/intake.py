"""Приём обращений из Яндекс-Формы (JSON-RPC POST) → создание Incident.

Этап отложенного приёма (deferred ingestion). Геокодер ещё не подключён —
адрес разбирается эвристикой (split по запятой). Функция толерантна к типам
входных значений: оператор маппит ответы формы на параметры JSON-RPC, но
гарантий типов нет (str / None / list).
"""

import logging
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Incident
from .audit import audit

logger = logging.getLogger(__name__)

# Форматы «времени фотофиксации», которые присылает форма (best-effort).
_PHOTO_TIME_FORMATS = (
    "%d.%m.%Y, %H:%M",
    "%d.%m.%Y %H:%M",
    "%Y-%m-%d %H:%M",
)

# Текстовые значения «наличие баков».
_BINS_TRUE = {"да", "yes", "true"}
_BINS_FALSE = {"нет", "no", "false"}


def _clean_str(value) -> str:
    """str | None | любое → стрипнутая строка ('' для None)."""
    if value is None:
        return ""
    return str(value).strip()


def _parse_address(full_address: str) -> tuple[str, str, str]:
    """Эвристика разбора адреса (геокодер отложен): split по запятой.

    ≥3 частей → region, city, street=остаток через ', ';
    ==2 → region, city, street='';
    иначе → region='', city='', street=full_address. Всё стрипнутое.
    """
    parts = [p.strip() for p in full_address.split(",")]
    if len(parts) >= 3:
        return parts[0], parts[1], ", ".join(parts[2:]).strip()
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return "", "", full_address.strip()


def _parse_bins(value) -> bool | None:
    """да/yes/true/True → True; нет/no/false/False → False; иначе None."""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text_value = str(value).strip().lower()
    if text_value in _BINS_TRUE:
        return True
    if text_value in _BINS_FALSE:
        return False
    return None


def _to_utc(dt: datetime) -> datetime:
    """Naive → трактуем как UTC (.replace); aware → перевод в UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_photo_time(value) -> datetime | None:
    """Best-effort разбор времени фотофиксации → tz-aware UTC. Иначе None."""
    text_value = _clean_str(value)
    if not text_value:
        return None
    for fmt in _PHOTO_TIME_FORMATS:
        try:
            return _to_utc(datetime.strptime(text_value, fmt))
        except ValueError:
            continue
    try:
        return _to_utc(datetime.fromisoformat(text_value))
    except ValueError:
        return None


def _parse_photo_urls(value) -> list[str]:
    """`photos` как list[str] ИЛИ строка (split по \\n , ; пробел).

    Оставляем только непустые http(s)-URL, не более 3.
    """
    if value is None:
        candidates: list = []
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = re.split(r"[\n,;\s]+", str(value))

    urls: list[str] = []
    for item in candidates:
        url = _clean_str(item)
        if url.startswith(("http://", "https://")):
            urls.append(url)
    return urls[:3]


async def create_incident_from_form(
    session: AsyncSession,
    params: dict,
    actor_user_id=None,
) -> Incident:
    """Создаёт Incident (source='form', status='new') из params Яндекс-Формы.

    Толерантна к отсутствующим/нетиповым значениям. flush() выполняется здесь,
    commit() — на стороне роутера.
    """
    params = params or {}

    full_address = _clean_str(params.get("full_address"))
    coords = _clean_str(params.get("coords"))
    fio = _clean_str(params.get("fio"))

    region, city, street = _parse_address(full_address)
    bins = _parse_bins(params.get("bins"))
    photo_time = _parse_photo_time(params.get("photo_time"))
    photo_urls = _parse_photo_urls(params.get("photos"))
    photos = max(0, min(3, len(photo_urls)))

    incident = Incident(
        source="form",
        status="new",
        fio=fio or "",
        region=region,
        city=city,
        street=street,
        coords=coords or "",
        photo_time=photo_time,
        photos=photos,
        photo_urls=photo_urls,
        bins=bins,
        received_at=datetime.now(timezone.utc),
    )
    session.add(incident)
    await session.flush()

    await audit(
        session,
        action="intake_form",
        entity_type="incident",
        entity_id=incident.id,
        after={"source": "form", "fio": fio, "full_address": full_address},
        actor_user_id=actor_user_id,
        actor_type="system",
    )
    return incident
