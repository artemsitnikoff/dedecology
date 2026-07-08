"""Эндпоинты настроек почтового сервера (SMTP) — раздел «Настройки», ТОЛЬКО admin.

Монтируется в router.py с prefix="/settings/smtp" и dependencies=[Depends(require_admin)]
— гвард роли на уровне включения роутера. Тонкий слой: валидация в схеме → вызов
сервиса → возврат статуса (пароль наружу не течёт). Итоговые пути:
  GET  /api/v1/settings/smtp            — статус
  POST /api/v1/settings/smtp/config     — сохранить конфиг
  POST /api/v1/settings/smtp/test       — тестовая отправка
  POST /api/v1/settings/smtp/disconnect — отключить
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...deps import get_current_user
from ...models import User
from ...schemas.base import MessageResult
from ...schemas.smtp import SmtpConfigRequest, SmtpTestRequest
from ...services import smtp as smtp_service

router = APIRouter()

TAG = "Настройки · Почтовый сервер (SMTP)"


@router.get("", tags=[TAG])
async def get_smtp_status(session: AsyncSession = Depends(get_db)):
    """Текущее состояние SMTP (без пароля)."""
    return await smtp_service.get_status(session)


@router.post("/config", tags=[TAG])
async def save_smtp_config(
    data: SmtpConfigRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Сохраняет настройки SMTP и возвращает обновлённый статус."""
    await smtp_service.save_config(
        session,
        current_user.id,
        host=data.host,
        port=data.port,
        encryption=data.encryption,
        username=data.username,
        password=data.password,
        from_email=data.from_email,
        from_name=data.from_name,
    )
    await session.commit()
    return await smtp_service.get_status(session)


@router.post("/test", tags=[TAG])
async def send_smtp_test(
    data: SmtpTestRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отправляет тестовое письмо (сервис коммитит сам — исход теста сохраняется всегда)."""
    return await smtp_service.send_test_email(session, current_user.id, to=data.to)


@router.post("/disconnect", response_model=MessageResult, tags=[TAG])
async def disconnect_smtp(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отключает SMTP (конфиг сохраняется, статус сбрасывается)."""
    await smtp_service.disconnect(session, current_user.id)
    await session.commit()
    return MessageResult(message="SMTP отключён")
