"""Публичный приём вебхуков Яндекс-Формы (JSON-RPC POST) → Incident.

ВАЖНО: эндпоинт НЕ требует Bearer-аутентификации (нет get_current_user) — это
внешний вебхук. Самозащита: общий секрет в заголовке X-Intake-Token
(constant-time сравнение). Тело логируется на INFO, чтобы первый реальный
сабмит можно было осмотреть в `docker compose logs backend` — конверт Яндекса
недокументирован, разбираем толерантно.
"""

import hmac
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...core.errors import AppError, ForbiddenError, NotFoundError, ValidationError
from ...database import get_db
from ...services import dadata as dadata_service
from ...services import intake as intake_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Имя файла фото: числовой индекс + опц. суффикс _thumb, только .jpg (анти-traversal).
# Все фото пере-кодируются в JPEG при загрузке: FULL `{i}.jpg`, THUMB `{i}_thumb.jpg`.
_PHOTO_FILENAME_RE = re.compile(r"^[0-9]+(_thumb)?\.jpg$")
# Минимальная длина запроса для подсказок адреса.
_SUGGEST_MIN_LEN = 3
# Потолок count в подсказках (защита от перебора DaData).
_SUGGEST_MAX_COUNT = 15


@router.post("/yandex")
async def yandex_intake(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Принимает JSON-RPC сабмит Яндекс-Формы и создаёт инцидент (source='form').

    Возвращает JSON-RPC-подобный result, чтобы «показать результат» в Яндексе
    отрабатывало.
    """
    # Гейт по токену (общий секрет в заголовке).
    if settings.YANDEX_INTAKE_TOKEN is None:
        raise AppError(
            code="INTAKE_DISABLED",
            message="Intake not configured",
            status_code=503,
        )
    header_token = request.headers.get("X-Intake-Token")
    if not header_token or not hmac.compare_digest(
        header_token, settings.YANDEX_INTAKE_TOKEN
    ):
        raise ForbiddenError("Неверный токен приёма")

    # Тело: толерантный разбор JSON-RPC-конверта.
    try:
        body = await request.json()
    except Exception:
        raise ValidationError("Тело запроса не является корректным JSON")

    logger.debug("yandex intake raw: %s", body)

    if isinstance(body, dict) and isinstance(body.get("params"), dict):
        params = body["params"]
    elif isinstance(body, dict):
        params = body
    else:
        params = {}

    incident = await intake_service.create_incident_from_form(session, params)
    await session.commit()

    return {
        "jsonrpc": "2.0",
        "id": body.get("id") if isinstance(body, dict) else None,
        "result": {"ok": True, "incident_id": str(incident.id)},
    }


@router.get("/suggest/address")
async def suggest_address(
    q: str = "",
    kind: str = "full",
    region: str | None = None,
    city: str | None = None,
    count: int = 8,
):
    """ПУБЛИЧНО: подсказки адреса для автозаполнения формы волонтёра.

    Ключ DaData остаётся на сервере. Без ключа / при q<3 символов / при сбое
    DaData отдаём пустой список (форма деградирует до ручного ввода).

    kind ограничивает уровень подсказок (bounded suggest):
    - "region"  — только регионы;
    - "city"    — города/населённые пункты (в пределах region, если задан);
    - "street"  — улицы/дома (в пределах region [+ city], если заданы);
    - "full"/иное — полный адрес (поведение по умолчанию).
    """
    if len(q.strip()) < _SUGGEST_MIN_LEN:
        return {"suggestions": []}
    count = max(1, min(count, _SUGGEST_MAX_COUNT))

    from_bound: str | None = None
    to_bound: str | None = None
    locations: list[dict] | None = None
    if kind == "region":
        from_bound, to_bound = "region", "region"
    elif kind == "city":
        from_bound, to_bound = "city", "settlement"
        if region:
            locations = [{"region": region}]
    elif kind == "street":
        from_bound, to_bound = "street", "house"
        if region or city:
            locations = [
                {
                    k: v
                    for k, v in (("region", region), ("city", city))
                    if v
                }
            ]
    # "full"/иное — bounds/locations остаются None (текущее поведение).

    suggestions = await dadata_service.suggest_address(
        q,
        count,
        from_bound,
        to_bound,
        locations,
    )
    return {"suggestions": suggestions}


@router.post("/form")
async def public_form(
    session: AsyncSession = Depends(get_db),
    fio: str = Form(""),
    full_address: str = Form(""),
    region: str = Form(""),
    city: str = Form(""),
    street: str = Form(""),
    coords: str = Form(""),
    photo_time: str = Form(""),
    bins: str = Form(""),
    website: str = Form(""),  # honeypot — у людей всегда пусто
    photos: list[UploadFile] = File(default=[]),
):
    """ПУБЛИЧНО: приём обращения из формы волонтёра (multipart/form-data).

    website — honeypot: если заполнен, это бот → отдаём ok, но ничего не создаём.
    """
    if website.strip():
        logger.info("intake public form honeypot triggered — dropping submission")
        return {"ok": True}

    incident = await intake_service.create_incident_from_public_form(
        session,
        fio=fio,
        full_address=full_address,
        region=region,
        city=city,
        street=street,
        coords=coords,
        photo_time=photo_time,
        bins=bins,
        photo_files=photos,
    )
    await session.commit()
    return {"ok": True, "incident_id": str(incident.id)}


@router.get("/photo/{incident_id}/{filename}")
async def get_photo(incident_id: str, filename: str):
    """ПУБЛИЧНО: отдаёт байты фото обращения. Жёсткий анти-traversal.

    incident_id обязан быть UUID, filename — `^[0-9]+(_thumb)?\\.jpg$`
    (FULL `{i}.jpg` или THUMB `{i}_thumb.jpg`), итоговый путь обязан остаться
    внутри каталога incidents.
    """
    try:
        uuid.UUID(incident_id)
    except (ValueError, AttributeError, TypeError):
        raise NotFoundError("Фото")
    if not _PHOTO_FILENAME_RE.match(filename):
        raise NotFoundError("Фото")

    base_dir = (Path(settings.STORAGE_DIR) / "incidents").resolve()
    path = (base_dir / incident_id / filename).resolve()
    if base_dir not in path.parents:
        raise NotFoundError("Фото")
    if not path.is_file():
        raise NotFoundError("Фото")

    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )
