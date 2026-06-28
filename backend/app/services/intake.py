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
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.errors import ValidationError
from ..models import Incident
from .audit import audit
from .dadata import clean_address
from . import parse_log
from .incident_parse import ai_parse_incident

logger = logging.getLogger(__name__)

_MAX_PHOTOS = 3
_MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10 MB (лимит исходного загружаемого файла)
_PHOTO_CHUNK = 64 * 1024

# Параметры серверного ресайза (фото пере-кодируются в JPEG при загрузке):
# FULL — версия для просмотра, THUMB — превью для списков/карты.
_FULL_MAX_SIDE = (1600, 1600)
_FULL_QUALITY = 85
_THUMB_MAX_SIDE = (400, 400)
_THUMB_QUALITY = 80
_WHITE = (255, 255, 255)

# Лимиты длины текстовых полей = ширине колонок БД. Отсекаем over-long значение,
# чтобы оно не вызвало DataError/500 на INSERT (легитимные данные укладываются).
_FIELD_LIMITS = {
    "fio": 255,
    "region": 255,
    "city": 255,
    "street": 500,
    "coords": 64,
    "msg": 120,
}


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


# Время фотофиксации, извлечённое AI, приходит «голым» в формате ЧЧ:ММ.
_HHMM_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _hhmm_today_utc(value) -> datetime | None:
    """ЧЧ:ММ → сегодня@ЧЧ:ММ (tz-aware UTC). None, если формат не совпал."""
    m = _HHMM_RE.match(_clean_str(value))
    if not m:
        return None
    return datetime.now(timezone.utc).replace(
        hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0
    )


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


# Сентинел «ai не передан» — отличает «парсить самим» от «передали None
# (AI-разбор не дал результата) — повторно НЕ дёргать CLI».
_AI_UNSET: object = object()


async def resolve_address(
    text: str, ai: "dict | None | object" = _AI_UNSET
) -> tuple[str, str, str, str]:
    """Разбор адреса из свободного текста → (region, city, street, coords).

    Единая логика, переиспользуемая приёмом из Макс-бота и командой reprocess:
      1. AI (ai_parse_incident) извлекает регион/город/улицу/координаты;
      2. если AI дал адрес → склейка региона+города+улицы и стандартизация через
         DaData Clean (clean_address): её поля и координаты (геокод) авторитетны;
         если DaData недоступна — берём поля AI как есть (+ координаты из AI);
      3. если AI ничего не дал → clean_address(raw); недоступна → эвристика
         _parse_address (coords пустые).

    Приоритет координат: DaData Clean > координаты AI > "".

    `ai` можно передать готовым — create_incident_from_max парсит его один раз
    (тот же ai нужен и для photo_time) и отдаёт сюда, чтобы НЕ дёргать CLI
    повторно. По умолчанию (`_AI_UNSET`) разбор делается здесь. Логирует, КАКОЙ
    путь сработал (ai+dadata / ai-only / dadata-raw / heuristic) — диагностика в
    проде «жива ли нейронка». Любой сбой AI/DaData деградирует на фолбэк и
    НИКОГДА не бросает исключений.
    """
    raw_text = _clean_str(text)

    if ai is _AI_UNSET:
        try:
            ai = await ai_parse_incident(raw_text)
        except Exception as e:  # noqa: BLE001 — AI не должен ронять разбор
            logger.warning(
                "[resolve_address] ai_parse_incident сбой: %s: %s", type(e).__name__, e
            )
            ai = None

    ai_dict: dict | None = ai if isinstance(ai, dict) else None

    region = city = street = coords = ""
    path = "—"
    resolved = False
    try:
        if ai_dict and (
            _clean_str(ai_dict.get("region"))
            or _clean_str(ai_dict.get("city"))
            or _clean_str(ai_dict.get("street"))
        ):
            addr = ", ".join(
                p
                for p in (
                    _clean_str(ai_dict.get("region")),
                    _clean_str(ai_dict.get("city")),
                    _clean_str(ai_dict.get("street")),
                )
                if p
            )
            cleaned = await clean_address(addr)
            if cleaned:
                # DaData авторитетна: стандартизированные поля + геокод.
                region = _clean_str(cleaned.get("region"))
                city = _clean_str(cleaned.get("city"))
                street = _clean_str(cleaned.get("street"))
                coords = _clean_str(cleaned.get("coords")) or _clean_str(
                    ai_dict.get("coords")
                )
                path = "ai+dadata"
                logger.info("[resolve_address] путь=ai+dadata")
            else:
                # DaData недоступна → поля AI как есть (+ координаты из текста).
                region = _clean_str(ai_dict.get("region"))
                city = _clean_str(ai_dict.get("city"))
                street = _clean_str(ai_dict.get("street"))
                coords = _clean_str(ai_dict.get("coords"))
                path = "ai-only"
                logger.info("[resolve_address] путь=ai-only (DaData недоступна)")
            resolved = True
    except Exception as e:  # noqa: BLE001 — DaData/разбор не должны ронять приём
        logger.warning("[resolve_address] AI-адрес сбой: %s: %s", type(e).__name__, e)
        resolved = False

    if not resolved:
        # Фолбэк без AI: DaData Clean(text) → эвристика.
        try:
            cleaned = await clean_address(raw_text)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "[resolve_address] clean_address сбой: %s: %s", type(e).__name__, e
            )
            cleaned = None
        if cleaned:
            region = _clean_str(cleaned.get("region"))
            city = _clean_str(cleaned.get("city"))
            street = _clean_str(cleaned.get("street"))
            coords = _clean_str(cleaned.get("coords"))
            path = "dadata-raw"
            logger.info("[resolve_address] путь=dadata-raw")
        else:
            region, city, street = _parse_address(raw_text)
            coords = ""
            path = "heuristic"
            logger.info("[resolve_address] путь=heuristic")

    parse_log.log_resolved(raw_text, path, region, city, street, coords)
    return region, city, street, coords


async def create_incident_from_max(
    session: AsyncSession,
    *,
    text: str,
    msg_id: str,
    sender_name: str,
    photo_files: list,
    msg_url: str = "",
    photo_time=None,
    actor_user_id=None,
) -> Incident:
    """Создаёт Incident (source='max') из сабмита Макс-бота.

    Адрес приходит свободным текстом. Разбор адреса:
      1. claude CLI (ai_parse_incident) извлекает регион/город/улицу/координаты/
         время из свободного текста;
      2. если AI дал адрес — склеиваем его и стандартизируем через DaData Clean
         (clean_address): координаты DaData авторитетны (геокодер); если DaData
         недоступна — берём поля AI как есть (+ координаты из текста, если AI их
         нашёл);
      3. если AI недоступен — текущий путь: clean_address(text) → эвристика
         _parse_address (coords пустые).

    Приоритет координат: DaData Clean > координаты из AI > "".
    Время фотофиксации: AI-время ЧЧ:ММ (сегодня@ЧЧ:ММ) переопределяет переданное;
    иначе разбираем photo_time из запроса. Любой сбой AI/DaData деградирует на
    фолбэк (log + fall through) и НИКОГДА не роняет приём. flush() здесь,
    commit() — в роутере.
    """
    raw_text = _clean_str(text)
    fio = _clean_str(sender_name)
    msg = _clean_str(msg_id) or None
    # Готовый https-URL сообщения (Message.url); для лички с ботом обычно пуст → None.
    msg_url_clean = _clean_str(msg_url) or None

    # AI-разбор свободного текста (graceful: любой сбой → None). Парсим здесь
    # ОДИН раз: ai нужен и для адреса (resolve_address), и для времени (ai.time);
    # отдаём готовый ai в resolve_address, чтобы не дёргать CLI повторно.
    ai: dict | None = None
    try:
        ai = await ai_parse_incident(raw_text)
    except Exception as e:  # noqa: BLE001 — AI не должен ронять приём
        logger.warning("[intake.max] ai_parse_incident сбой: %s: %s", type(e).__name__, e)
        ai = None

    region, city, street, coords = await resolve_address(raw_text, ai=ai)

    # Отсекаем текст до ширины колонок БД.
    fio = fio[: _FIELD_LIMITS["fio"]]
    region = region[: _FIELD_LIMITS["region"]]
    city = city[: _FIELD_LIMITS["city"]]
    street = street[: _FIELD_LIMITS["street"]]
    coords = coords[: _FIELD_LIMITS["coords"]]
    if msg is not None:
        msg = msg[: _FIELD_LIMITS["msg"]]

    # Время фотофиксации: AI-время ЧЧ:ММ переопределяет переданное.
    parsed_photo_time = _hhmm_today_utc(ai.get("time")) if ai else None
    if parsed_photo_time is None:
        parsed_photo_time = _parse_photo_time(photo_time)

    incident = Incident(
        source="max",
        status="new",
        fio=fio or "",
        region=region,
        city=city,
        street=street,
        coords=coords or "",
        photo_time=parsed_photo_time,
        photos=0,
        photo_urls=[],
        msg=msg,
        msg_url=msg_url_clean,
        received_at=datetime.now(timezone.utc),
    )
    session.add(incident)
    await session.flush()  # → incident.id

    photo_urls, count = await _process_photos(incident.id, photo_files)
    if count:
        incident.photo_urls = photo_urls
        incident.photos = count
        await session.flush()

    await audit(
        session,
        action="intake_max",
        entity_type="incident",
        entity_id=incident.id,
        after={"source": "max", "fio": fio, "msg": msg, "text": raw_text},
        actor_user_id=actor_user_id,
        actor_type="system",
    )
    return incident


async def _read_upload_bytes(upload) -> bytes:
    """Считывает поток загрузки целиком чанками с контролем размера ≤10 МБ.

    Превышение лимита / пустой файл → ValidationError. Возвращает сырые байты
    для последующей валидации и пере-кодирования через Pillow.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_PHOTO_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_PHOTO_BYTES:
            raise ValidationError(
                "Файл фото превышает 10 МБ",
                details={"filename": getattr(upload, "filename", None)},
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise ValidationError("Пустой файл фото")
    return data


def _decode_image(data: bytes, filename) -> Image.Image:
    """Открывает байты через Pillow → RGB-изображение с исправленной ориентацией.

    Pillow — авторитетный валидатор формата (клиентский Content-Type не в счёт):
    невалидные/неполные данные → ValidationError. EXIF-ориентация выправляется,
    прозрачность png/webp «сплющивается» на белый фон.
    """
    try:
        img = Image.open(BytesIO(data))
        img.load()  # форсируем декодирование — ловим усечённые/битые файлы
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ValidationError(
            "Файл не является изображением (jpg/png/webp)",
            details={"filename": filename},
        )

    img = ImageOps.exif_transpose(img)  # выправляем ориентацию по EXIF
    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        flattened = Image.new("RGB", rgba.size, _WHITE)
        flattened.paste(rgba, mask=rgba.split()[-1])
        return flattened
    return img.convert("RGB")


def _save_variant(img: Image.Image, dest: Path, max_side, quality: int) -> None:
    """Сохраняет уменьшенную (только downscale, аспект сохранён) JPEG-копию."""
    variant = img.copy()
    variant.thumbnail(max_side)  # пропорционально, апскейла не делает
    variant.save(dest, "JPEG", quality=quality, optimize=True)


async def _decode_uploads(photo_files: list) -> list[Image.Image]:
    """Валидирует и декодирует загруженные фото (без записи на диск).

    Фильтрует пустые поля, проверяет количество (≤3), читает байты с лимитом
    10 МБ, декодирует через Pillow (авторитетная проверка формата — multipart
    Content-Type не в счёт). Невалидное/лишнее фото → ValidationError. Вызывается
    ДО создания инцидента, чтобы битый файл отбивался 400 без записи в БД.
    """
    photo_files = [f for f in (photo_files or []) if getattr(f, "filename", None)]
    if len(photo_files) > _MAX_PHOTOS:
        raise ValidationError(
            f"Можно загрузить не более {_MAX_PHOTOS} фото",
            details={"count": len(photo_files)},
        )
    decoded: list[Image.Image] = []
    for upload in photo_files:
        data = await _read_upload_bytes(upload)
        decoded.append(_decode_image(data, getattr(upload, "filename", None)))
    return decoded


def _store_decoded(incident_id, decoded: list[Image.Image]) -> tuple[list[str], int]:
    """Сохраняет уже декодированные фото в {STORAGE_DIR}/incidents/{id}/.

    Каждое фото пере-кодируется в JPEG: FULL `{i}.jpg` (просмотр) + THUMB
    `{i}_thumb.jpg` (превью). Возвращает (photo_urls, count). При сбое записи
    частично созданный каталог удаляется (не оставляем мусор на диске).
    """
    if not decoded:
        return [], 0

    photo_urls: list[str] = []
    incident_dir = _incidents_dir() / str(incident_id)
    try:
        incident_dir.mkdir(parents=True, exist_ok=True)
        for i, img in enumerate(decoded):
            _save_variant(img, incident_dir / f"{i}.jpg", _FULL_MAX_SIDE, _FULL_QUALITY)
            _save_variant(
                img,
                incident_dir / f"{i}_thumb.jpg",
                _THUMB_MAX_SIDE,
                _THUMB_QUALITY,
            )
            photo_urls.append(f"/api/v1/intake/photo/{incident_id}/{i}.jpg")
    except Exception:
        shutil.rmtree(incident_dir, ignore_errors=True)
        raise

    return photo_urls, len(photo_urls)


async def _process_photos(incident_id, photo_files: list) -> tuple[list[str], int]:
    """Полный конвейер фото: валидация/декод + сохранение → (photo_urls, count).

    Переиспользуемый хелпер (Макс-бот). Невалидное фото → ValidationError.
    """
    decoded = await _decode_uploads(photo_files)
    return _store_decoded(incident_id, decoded)


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

    # Валидируем/декодируем фото ДО создания инцидента — битый файл отбивается
    # 400 без записи в БД.
    decoded = await _decode_uploads(photo_files)

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

    photo_urls, count = _store_decoded(incident.id, decoded)
    if count:
        incident.photo_urls = photo_urls
        incident.photos = count
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
