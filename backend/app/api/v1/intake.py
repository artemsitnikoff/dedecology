"""Публичный приём вебхуков Яндекс-Формы (JSON-RPC POST) → Incident.

ВАЖНО: эндпоинт НЕ требует Bearer-аутентификации (нет get_current_user) — это
внешний вебхук. Самозащита: общий секрет в заголовке X-Intake-Token
(constant-time сравнение). Тело логируется на INFO, чтобы первый реальный
сабмит можно было осмотреть в `docker compose logs backend` — конверт Яндекса
недокументирован, разбираем толерантно.
"""

import hmac
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...core.errors import AppError, ForbiddenError, ValidationError
from ...database import get_db
from ...services import intake as intake_service

logger = logging.getLogger(__name__)

router = APIRouter()


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

    logger.info("yandex intake raw: %s", body)

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
