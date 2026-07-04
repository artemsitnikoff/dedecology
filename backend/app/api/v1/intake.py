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

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...core.errors import AppError, ForbiddenError, NotFoundError, ValidationError
from ...database import get_db
from ...deps import get_optional_volunteer
from ...models import Volunteer
from ...schemas.incident import (
    MarkNotified,
    MarkNotifiedResult,
    PendingNotifyResponse,
)
from ...schemas.mno import MnoFormPointsResponse, MnoVolunteerCreate
from ...services import dadata as dadata_service
from ...services import incident as incident_service
from ...services import incident_type as incident_type_service
from ...services import intake as intake_service
from ...services import mno as mno_service
from ...services import quotes as quotes_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_intake_token(request: Request) -> None:
    """Гейт server-to-server по общему секрету X-Intake-Token (как /yandex, /max).

    Токен не задан на сервере → 503 INTAKE_DISABLED; не совпал/отсутствует → 403.
    Сравнение constant-time (hmac.compare_digest).
    """
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

# Имя файла фото: числовой индекс + опц. суффикс _thumb, только .jpg (анти-traversal).
# Все фото пере-кодируются в JPEG при загрузке: FULL `{i}.jpg`, THUMB `{i}_thumb.jpg`.
_PHOTO_FILENAME_RE = re.compile(r"^[0-9]+(_thumb)?\.jpg$")
# Минимальная длина запроса для подсказок адреса.
_SUGGEST_MIN_LEN = 3
# Потолок count в подсказках (защита от перебора DaData).
_SUGGEST_MAX_COUNT = 15


@router.post("/yandex", tags=["Приём вебхуков (server-to-server)"])
async def yandex_intake(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Принимает JSON-RPC сабмит Яндекс-Формы и создаёт инцидент (source='form').

    Возвращает JSON-RPC-подобный result, чтобы «показать результат» в Яндексе
    отрабатывало.
    """
    # Гейт по токену (общий секрет в заголовке).
    _require_intake_token(request)

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


@router.get("/suggest/address", tags=["Загрузка фото"])
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


@router.get("/incident-types", tags=["Отправка фотоотчёта"])
async def incident_types(session: AsyncSession = Depends(get_db)):
    """ПУБЛИЧНО: справочник типов инцидента [{code, label}] для дропдауна формы/фильтра.

    Источник — редактируемый справочник в БД (таблица incident_types); подпись фронт
    резолвит по коду. Контракт ответа сохранён ([{code, label}] в порядке sort_order),
    чтобы форма/фильтр/карточка не меняли свой fetch. Публичный (intake-роутер без
    auth) — нужен неавторизованной форме волонтёра.
    """
    types = await incident_type_service.list_types(session)
    return [{"code": t.code, "label": t.label} for t in types]


@router.get(
    "/mno-points",
    response_model=MnoFormPointsResponse,
    tags=["Отправка фотоотчёта"],
)
async def mno_points(
    bbox: str = Query(
        "",
        description="Видимая область карты «minLat,minLon,maxLat,maxLon» (обязателен)",
    ),
    session: AsyncSession = Depends(get_db),
):
    """ПУБЛИЧНО: точки МНО в видимой области карты для выбора площадки в форме.

    Публичный (intake-роутер без auth), как incident-types — нужен неавторизованной
    форме волонтёра. bbox ОБЯЗАТЕЛЕН: без валидного bbox отдаём пустой список, чтобы
    не тянуть весь реестр МНО в неавторизованный эндпоинт (см. list_form_points).
    """
    return await mno_service.list_form_points(session, bbox=bbox)


@router.post("/mno", tags=["Отправка фотоотчёта"])
async def create_volunteer_mno(
    session: AsyncSession = Depends(get_db),
    volunteer: Volunteer | None = Depends(get_optional_volunteer),
    address: str = Form(""),
    coords: str = Form(""),
    name: str = Form(""),
    region_code: str = Form(""),
    city: str = Form(""),
    comment: str = Form(""),
    website: str = Form(""),  # honeypot — у людей всегда пусто
    photos: list[UploadFile] = File(default=[]),
):
    """ПУБЛИЧНО: волонтёр добавляет МНО (multipart/form-data), если нужного нет на карте.

    В ряду с /intake/form — без auth, honeypot website (заполнен → бот → ok, ничего не
    создаём). Иначе создаём МНО (source='volunteer', synced=False, fgis_id=None) с
    необязательными комментарием (≤500) и фото, возвращаем карточку (MnoDetail) —
    приложение кладёт id в mno_id отчёта. Тело — multipart (а не JSON), т.к. несёт файлы
    фото. Пустые address/coords → 400 VALIDATION_ERROR; невалидное фото (тип/размер/>3) →
    400 (обе проверки в сервисе, до записи).

    Авторство: если пришёл валидный volunteer-токен (get_optional_volunteer) — пишем
    volunteer_id (МНО попадёт в «Мои МНО» приложения); нет/битый токен → аноним (NULL).
    """
    if website.strip():
        logger.info("intake public mno honeypot triggered — dropping submission")
        return {"ok": True}
    data = MnoVolunteerCreate(
        address=address,
        coords=coords,
        name=name,
        region_code=region_code,
        city=city,
        comment=comment,
    )
    mno = await mno_service.create_mno_from_volunteer(
        session,
        data,
        photo_files=photos,
        volunteer_id=(volunteer.id if volunteer else None),
    )
    await session.commit()
    return mno


@router.post("/form", tags=["Отправка фотоотчёта"])
async def public_form(
    session: AsyncSession = Depends(get_db),
    volunteer: Volunteer | None = Depends(get_optional_volunteer),
    fio: str = Form(""),
    full_address: str = Form(""),
    region: str = Form(""),
    city: str = Form(""),
    street: str = Form(""),
    coords: str = Form(""),
    mno_reg: str = Form(""),
    mno_id: str = Form(""),
    incident_type: str = Form(""),
    comment: str = Form(""),
    photo_time: str = Form(""),
    bins: str = Form(""),
    website: str = Form(""),  # honeypot — у людей всегда пусто
    photos: list[UploadFile] = File(default=[]),
):
    """ПУБЛИЧНО: приём обращения из формы волонтёра (multipart/form-data).

    website — honeypot: если заполнен, это бот → отдаём ok, но ничего не создаём.

    Авторство: если пришёл валидный volunteer-токен (get_optional_volunteer) — пишем
    volunteer_id (отчёт попадёт в «Мои отчёты» приложения); нет/битый токен → аноним
    (NULL), веб-форма остаётся анонимной.
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
        mno_reg=mno_reg,
        mno_id=mno_id,
        incident_type=incident_type,
        comment=comment,
        photo_time=photo_time,
        bins=bins,
        photo_files=photos,
        volunteer_id=(volunteer.id if volunteer else None),
    )
    await session.commit()
    # Цитату генерируем ПОСЛЕ commit — медленный/упавший CLI не блокирует запись.
    quote = await quotes_service.nature_quote()
    # Сохраняем цитату на инциденте 2-м коммитом (запись уже зафиксирована выше).
    incident.quote = quote
    await session.commit()
    return {"ok": True, "incident_id": str(incident.id), "quote": quote}


@router.post("/max", tags=["Приём вебхуков (server-to-server)"])
async def max_intake(
    request: Request,
    session: AsyncSession = Depends(get_db),
    text: str = Form(""),
    msg_id: str = Form(""),
    msg_url: str = Form(""),
    sender_name: str = Form(""),
    photo_time: str = Form(""),
    photos: list[UploadFile] = File(default=[]),
):
    """Приём обращения из Макс-бота (multipart/form-data) → Incident(source='max').

    Вызывается сервером Макс-бота server-to-server. Самозащита — общий секрет
    в заголовке X-Intake-Token (тот же гейт, что у /yandex): токен не задан на
    сервере → 503; не совпал → 403. Адрес из текста разбирается DaData Clean API
    (с эвристическим фолбэком). Возвращает {"ok": True, "incident_id": ...}.
    """
    # Гейт по токену (общий секрет в заголовке) — зеркалит /yandex.
    _require_intake_token(request)

    incident = await intake_service.create_incident_from_max(
        session,
        text=text,
        msg_id=msg_id,
        msg_url=msg_url,
        sender_name=sender_name,
        photo_time=photo_time or None,
        photo_files=photos,
    )
    await session.commit()
    # Цитату генерируем ПОСЛЕ commit — медленный/упавший CLI не блокирует запись.
    quote = await quotes_service.nature_quote()
    # Сохраняем цитату на инциденте 2-м коммитом (запись уже зафиксирована выше).
    incident.quote = quote
    await session.commit()
    return {"ok": True, "incident_id": str(incident.id), "quote": quote}


@router.get(
    "/pending-notify",
    response_model=PendingNotifyResponse,
    tags=["Приём вебхуков (server-to-server)"],
)
async def pending_notify(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Очередь инцидентов для уведомления в группу Макс (notified_at IS NULL).

    Server-to-server для воркера Макс-бота: гейт X-Intake-Token (как /max).
    Старейшие первыми (created_at ASC), не более 20 за вызов.
    """
    _require_intake_token(request)
    incidents = await incident_service.list_pending_notify(session, limit=20)
    return PendingNotifyResponse(incidents=incidents)


@router.post(
    "/mark-notified",
    response_model=MarkNotifiedResult,
    tags=["Приём вебхуков (server-to-server)"],
)
async def mark_notified(
    request: Request,
    payload: MarkNotified,
    session: AsyncSession = Depends(get_db),
):
    """Помечает инциденты как уведомлённые (notified_at = now). Гейт X-Intake-Token.

    Идемпотентно: учитывает только ещё не уведомлённые id. Возвращает {"marked": N}.
    """
    _require_intake_token(request)
    marked = await incident_service.mark_notified(session, payload.ids)
    await session.commit()
    return MarkNotifiedResult(marked=marked)


@router.get("/photo/{incident_id}/{filename}", tags=["Загрузка фото"])
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


@router.get("/mno-photo/{mno_id}/{filename}", tags=["Загрузка фото"])
async def get_mno_photo(mno_id: str, filename: str):
    """ПУБЛИЧНО: отдаёт байты фото волонтёрского МНО. Жёсткий анти-traversal.

    Зеркалит get_photo (фото инцидентов), но каталог — {STORAGE_DIR}/mno/{mno_id}/.
    mno_id обязан быть UUID, filename — `^[0-9]+(_thumb)?\\.jpg$` (FULL `{i}.jpg` или
    THUMB `{i}_thumb.jpg`), итоговый путь обязан остаться внутри каталога mno.
    """
    try:
        uuid.UUID(mno_id)
    except (ValueError, AttributeError, TypeError):
        raise NotFoundError("Фото")
    if not _PHOTO_FILENAME_RE.match(filename):
        raise NotFoundError("Фото")

    base_dir = (Path(settings.STORAGE_DIR) / "mno").resolve()
    path = (base_dir / mno_id / filename).resolve()
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
