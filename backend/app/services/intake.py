"""Приём обращений из Яндекс-Формы (JSON-RPC POST) → создание Incident.

Этап отложенного приёма (deferred ingestion). Геокодер ещё не подключён —
адрес разбирается эвристикой (split по запятой). Функция толерантна к типам
входных значений: оператор маппит ответы формы на параметры JSON-RPC, но
гарантий типов нет (str / None / list).
"""

import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.errors import ValidationError
from ..models import Incident
from .audit import audit

logger = logging.getLogger(__name__)

_MAX_PHOTOS = 3
_MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10 MB
_PHOTO_CHUNK = 64 * 1024
# Кол-во первых байт файла, достаточное для проверки сигнатуры формата.
_PHOTO_HEADER_BYTES = 16

# Лимиты длины текстовых полей = ширине колонок БД. Отсекаем over-long значение,
# чтобы оно не вызвало DataError/500 на INSERT (легитимные данные укладываются).
_FIELD_LIMITS = {
    "fio": 255,
    "region": 255,
    "city": 255,
    "street": 500,
    "coords": 64,
}


def _detect_image_ext(header: bytes) -> str | None:
    """Определяет реальный формат изображения по «магическим» байтам.

    Клиентский multipart Content-Type не доверяется — расширение выводится из
    сигнатуры. JPEG → 'jpg', PNG → 'png', WebP → 'webp'; иначе None.
    """
    if header[:3] == b"\xff\xd8\xff":
        return "jpg"
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(header) >= 12 and header[0:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def _incidents_dir() -> Path:
    """Базовый каталог хранения фото обращений: {STORAGE_DIR}/incidents."""
    return Path(settings.STORAGE_DIR) / "incidents"

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


async def _save_photo(upload, dest: Path, header: bytes) -> None:
    """Пишет уже считанный header + дочитывает остаток потока чанками.

    header — первые байты, считанные ранее для проверки сигнатуры (их нельзя
    потерять). Контроль общего размера ≤10 МБ. Слишком большой файл →
    ValidationError (частично записанный файл удаляет вызывающая сторона
    вместе со всем каталогом инцидента).
    """
    written = 0
    with dest.open("wb") as out:
        if header:
            written += len(header)
            out.write(header)
        while True:
            chunk = await upload.read(_PHOTO_CHUNK)
            if not chunk:
                break
            written += len(chunk)
            if written > _MAX_PHOTO_BYTES:
                raise ValidationError(
                    "Файл фото превышает 10 МБ",
                    details={"filename": getattr(upload, "filename", None)},
                )
            out.write(chunk)
    if written == 0:
        raise ValidationError("Пустой файл фото")


async def create_incident_from_public_form(
    session: AsyncSession,
    *,
    fio: str,
    full_address: str,
    region: str,
    city: str,
    street: str,
    coords: str,
    photo_time,
    bins,
    photo_files: list,
    actor_user_id=None,
) -> Incident:
    """Создаёт Incident (source='form') из публичной формы волонтёра + фото.

    region/city/street берутся из явных полей, если непусты, иначе выводятся
    эвристикой из full_address. Фото валидируются (тип/размер/количество) и
    сохраняются в {STORAGE_DIR}/incidents/{id}/. flush() здесь, commit() —
    в роутере. Невалидные фото → ValidationError + очистка частичного каталога.
    """
    fio = _clean_str(fio)
    full_address = _clean_str(full_address)
    region = _clean_str(region)
    city = _clean_str(city)
    street = _clean_str(street)
    coords = _clean_str(coords)

    if not (region or city or street):
        region, city, street = _parse_address(full_address)

    # Отсекаем текст до ширины колонок БД (после вывода region/city/street).
    fio = fio[: _FIELD_LIMITS["fio"]]
    region = region[: _FIELD_LIMITS["region"]]
    city = city[: _FIELD_LIMITS["city"]]
    street = street[: _FIELD_LIMITS["street"]]
    coords = coords[: _FIELD_LIMITS["coords"]]

    parsed_bins = _parse_bins(bins)
    parsed_photo_time = _parse_photo_time(photo_time)

    photo_files = [f for f in (photo_files or []) if getattr(f, "filename", None)]
    if len(photo_files) > _MAX_PHOTOS:
        raise ValidationError(
            f"Можно загрузить не более {_MAX_PHOTOS} фото",
            details={"count": len(photo_files)},
        )
    # Не доверяем multipart Content-Type: читаем первые байты и проверяем
    # реальную сигнатуру. Расширение определяем по формату, а не по заголовку.
    validated: list[tuple] = []  # (upload, ext, header_bytes)
    for upload in photo_files:
        header = await upload.read(_PHOTO_HEADER_BYTES)
        ext = _detect_image_ext(header)
        if ext is None:
            raise ValidationError(
                "Файл не является изображением (jpg/png/webp)",
                details={"filename": getattr(upload, "filename", None)},
            )
        validated.append((upload, ext, header))

    incident = Incident(
        source="form",
        status="new",
        fio=fio or "",
        region=region,
        city=city,
        street=street,
        coords=coords or "",
        photo_time=parsed_photo_time,
        photos=0,
        photo_urls=[],
        bins=parsed_bins,
        received_at=datetime.now(timezone.utc),
    )
    session.add(incident)
    await session.flush()  # → incident.id

    photo_urls: list[str] = []
    if validated:
        incident_dir = _incidents_dir() / str(incident.id)
        try:
            incident_dir.mkdir(parents=True, exist_ok=True)
            for i, (upload, ext, header) in enumerate(validated):
                filename = f"{i}.{ext}"
                await _save_photo(upload, incident_dir / filename, header)
                photo_urls.append(
                    f"/api/v1/intake/photo/{incident.id}/{filename}"
                )
        except Exception:
            # Очистка частично записанного каталога — не оставляем мусор на диске.
            shutil.rmtree(incident_dir, ignore_errors=True)
            raise

        incident.photo_urls = photo_urls
        incident.photos = len(photo_urls)
        await session.flush()

    await audit(
        session,
        action="intake_public_form",
        entity_type="incident",
        entity_id=incident.id,
        after={"source": "form", "fio": fio, "full_address": full_address},
        actor_user_id=actor_user_id,
        actor_type="system",
    )
    return incident
