"""Роутеры событий посещения МНО (УТКО-совместимое API, ядро).

Три метода контракта ФГИС УТКО:
  • POST /reo-mno-events/api/v1/integration/truck-visit-events/query   — выдача событий;
  • POST /reo-mno-events/api/v1/integration/truck-visit-events/confirm — приём подтверждений;
  • POST /reo-mno-events/api/v1.0/video-events                         — приём видео-событий.

Вход разбирается СЫРЫМ JSON (request.json()) и валидируется вручную (app/utko/validate.py),
чтобы тексты ошибок совпадали с таблицами доки, а не с глобальным конвертом приложения.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from .. import errors, service, validate
from ..auth import require_utko_auth
from ..schemas import TruckVisitEventItem, VideoEventResult

router = APIRouter()

# URL задаётся полностью здесь (роутер подключается в app.main БЕЗ prefix).
_QUERY_URL = "/reo-mno-events/api/v1/integration/truck-visit-events/query"
_CONFIRM_URL = "/reo-mno-events/api/v1/integration/truck-visit-events/confirm"
_VIDEO_URL = "/reo-mno-events/api/v1.0/video-events"

_TAG = "УТКО-совместимое API"


async def _read_json(request: Request):
    """Прочитать тело как JSON; битый JSON → 400 (формат УТКО)."""
    try:
        return await request.json()
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        raise errors.bad_request("Некорректный JSON в теле запроса")


@router.post(_QUERY_URL, tags=[_TAG])
async def truck_visit_events_query(
    request: Request,
    _auth: dict = Depends(require_utko_auth),
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Получение списка последних событий посещения МНО.

    Тело: {filter:{fromDate(обяз),toDate(опц)}, take, skip}. Пусто в БД → count 0.
    """
    body = await _read_json(request)
    params = validate.validate_query(body)

    total, rows = await service.query_truck_visit_events(
        session,
        from_date=params["from_date"],
        to_date=params["to_date"],
        take=params["take"],
        skip=params["skip"],
    )
    items = [TruckVisitEventItem.model_validate(r).model_dump_camel() for r in rows]
    return JSONResponse(status_code=200, content={"count": total, "items": items})


@router.post(_CONFIRM_URL, tags=[_TAG])
async def truck_visit_events_confirm(
    request: Request,
    _auth: dict = Depends(require_utko_auth),
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Приём подтверждений опустошения контейнера по событиям посещения.

    Тело — массив. Валидация по Таблице 2; при любой ошибке пакет не принимается
    (проверяем ВСЕ элементы до сохранения). Тело ответа контрактом не задано → 200 [].
    """
    body = await _read_json(request)
    raw_items = validate.require_list(body)

    # Фаза 1 — валидация формы + существования eventId по ВСЕМ элементам (ничего не пишем).
    validated: list[dict] = []
    for item in raw_items:
        norm = validate.validate_confirm_item(item)
        if not await service.event_exists(session, norm["event_id"]):
            raise errors.unknown_event()
        validated.append(norm)

    # Фаза 2 — сохранение (upsert по event_id).
    for norm in validated:
        await service.upsert_confirmation(session, norm)
    await session.commit()

    return JSONResponse(status_code=200, content=[])


@router.post(_VIDEO_URL, tags=[_TAG])
async def video_events(
    request: Request,
    _auth: dict = Depends(require_utko_auth),
    session: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Приём событий обработки видеопотока.

    Тело — массив. Валидация по Таблице 3; при наличии хотя бы одной ошибки НЕ принимается
    весь пакет (проверяем всё до сохранения). Ответ: [{externalEventId, videoEventUuid}].
    """
    body = await _read_json(request)
    raw_items = validate.require_list(body)

    # Фаза 1 — валидация формы + существования mnoId по ВСЕМ элементам (батч all-or-nothing).
    validated: list[dict] = []
    for item in raw_items:
        norm = validate.validate_video_item(item)
        if not await service.mno_exists(session, norm["mno_id"]):
            raise errors.unknown_mno(str(norm["mno_id"]))
        validated.append(norm)

    # Фаза 2 — сохранение; на каждый элемент генерируется videoEventUuid.
    results: list[dict] = []
    for norm in validated:
        row = await service.save_video_event(session, norm)
        # external_event_id уже строка|None — возвращаем verbatim (как пришло).
        results.append(
            VideoEventResult(
                external_event_id=norm["external_event_id"], video_event_uuid=row.id
            ).model_dump_camel()
        )
    await session.commit()

    return JSONResponse(status_code=200, content=results)
