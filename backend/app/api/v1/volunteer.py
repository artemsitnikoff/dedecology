"""Эндпоинты волонтёра (мобильное приложение), prefix /volunteer.

БЕЗ admin-гейта — это публичный/самообслуживаемый контур волонтёра: регистрация,
подтверждение почты, вход, восстановление пароля, онбординг и профиль. Тонкий слой:
валидация схемой → сервис/токены/SMTP → схема ответа.

Письма — через настроенный SMTP (Настройки → Почта). Если письмо НЕ ушло (SMTP не настроен
или отправка упала → email_sent=false), секрет кладём в ОТВЕТ: код подтверждения для регистрации/
resend, токен-ссылку для сброса пароля — чтобы поток можно было завершить (тест/интеграция).
Если ушло (True) — секрет в ответ НЕ кладём. Подтверждение почты — 4-значный код (OTP).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...deps import get_current_volunteer
from ...models import Volunteer
from ...core.security import create_volunteer_access_token
from ...schemas.base import Paginated
from ...schemas.incident import IncidentListItem
from ...schemas.mno import MnoDetail
from ...services import blocked_domain as blocked_domain_service
from ...services import incident as incident_service
from ...services import mno as mno_service
from ...schemas.volunteer import (
    OkResponse,
    VolunteerLogin,
    VolunteerLoginResponse,
    VolunteerOnboarding,
    VolunteerProfile,
    VolunteerRegister,
    VolunteerRegisterResponse,
    VolunteerResendRequest,
    VolunteerResendResponse,
    VolunteerResetPassword,
    VolunteerResetRequest,
    VolunteerResetRequestResponse,
    VolunteerVerifyEmail,
    VolunteerVerifyResponse,
)
from ...services.volunteer import (
    EMAIL_CODE_LENGTH,
    EMAIL_CODE_RESEND_COOLDOWN_SECONDS,
    authenticate,
    complete_onboarding,
    register,
    request_password_reset,
    resend_email_code,
    reset_password,
    send_email_code,
    send_reset_email,
    verify_email,
)

router = APIRouter()

_TAG = "Волонтёры (мобильное приложение)"


@router.get("/blocked-domains", response_model=list[str], tags=[_TAG])
async def volunteer_blocked_domains(session: AsyncSession = Depends(get_db)):
    """ПУБЛИЧНЫЙ (анонимный, без токена) стоп-лист почтовых доменов — для формы регистрации
    в приложении: клиент проверяет домен ДО отправки. Возвращает только имена доменов
    (без id/дат — админ-CRUD /blocked-domains остаётся под admin-гейтом)."""
    domains = await blocked_domain_service.list_domains(session)
    return [d.domain for d in domains]


@router.post("/register", response_model=VolunteerRegisterResponse, status_code=201, tags=[_TAG])
async def register_volunteer(
    data: VolunteerRegister,
    session: AsyncSession = Depends(get_db),
):
    """Регистрация волонтёра. Пароли не совпали → 400, дубль email → 409.

    Шлём 4-значный код подтверждения письмом; если письмо не ушло (нет SMTP) — код в ответе.
    """
    volunteer = await register(session, data)
    # Код выдаётся и (по возможности) отправляется письмом; commit сохраняет его в БД.
    sent = await send_email_code(session, volunteer)
    await session.commit()

    return VolunteerRegisterResponse(
        volunteer_id=volunteer.id,
        email=volunteer.email,
        email_sent=sent,
        code_length=EMAIL_CODE_LENGTH,
        resend_after=EMAIL_CODE_RESEND_COOLDOWN_SECONDS,
        email_verify_code=None if sent else volunteer.email_code,
    )


@router.post("/register/resend", response_model=VolunteerResendResponse, tags=[_TAG])
async def resend_volunteer_code(
    data: VolunteerResendRequest,
    session: AsyncSession = Depends(get_db),
):
    """Повторная отправка кода подтверждения. Рано → 429 RESEND_TOO_SOON (resend_after)."""
    email_sent, already_verified, volunteer = await resend_email_code(session, data.email)
    await session.commit()

    # Код кладём в ответ только если реально выдан новый и письмо не ушло.
    code = None
    if not email_sent and not already_verified and volunteer is not None:
        code = volunteer.email_code

    return VolunteerResendResponse(
        ok=True,
        email_sent=email_sent,
        already_verified=already_verified,
        code_length=EMAIL_CODE_LENGTH,
        resend_after=EMAIL_CODE_RESEND_COOLDOWN_SECONDS,
        email_verify_code=code,
    )


@router.post("/verify-email", response_model=VolunteerVerifyResponse, tags=[_TAG])
async def verify_volunteer_email(
    data: VolunteerVerifyEmail,
    session: AsyncSession = Depends(get_db),
):
    """Подтверждение почты по 4-значному коду. Истёк → 400 CODE_EXPIRED, неверный →
    400 INVALID_CODE (attempts_left), лимит попыток → 429 TOO_MANY_ATTEMPTS."""
    await verify_email(session, data.email, data.code)
    await session.commit()
    return VolunteerVerifyResponse(ok=True, email_verified=True)


@router.post("/login", response_model=VolunteerLoginResponse, tags=[_TAG])
async def login_volunteer(
    data: VolunteerLogin,
    session: AsyncSession = Depends(get_db),
):
    """Вход волонтёра. 401 неверные данные · 403 EMAIL_NOT_VERIFIED · 403 BLOCKED."""
    volunteer = await authenticate(session, data.email, data.password)
    # authenticate проставил last_seen_at (последняя авторизация) — фиксируем.
    await session.commit()
    access_token = create_volunteer_access_token(str(volunteer.id))
    return VolunteerLoginResponse(
        access_token=access_token,
        token_type="bearer",
        volunteer=VolunteerProfile.model_validate(volunteer),
    )


@router.post(
    "/password/reset-request",
    response_model=VolunteerResetRequestResponse,
    tags=[_TAG],
)
async def request_reset(
    data: VolunteerResetRequest,
    session: AsyncSession = Depends(get_db),
):
    """Запрос сброса пароля. Всегда ok=true (анти-энумерация); токен — только при !email_sent."""
    volunteer = await request_password_reset(session, data.email)

    # Неизвестный email — единый ответ без токена (не раскрываем наличие учётки).
    if volunteer is None:
        return VolunteerResetRequestResponse(ok=True, email_sent=False)

    # Токен/письмо — общий хелпер (тот же код, что у админ-триггера).
    email_sent, token, reset_url = await send_reset_email(session, volunteer)
    return VolunteerResetRequestResponse(
        ok=True,
        email_sent=email_sent,
        reset_token=None if email_sent else token,
        reset_url=None if email_sent else reset_url,
    )


@router.post("/password/reset", response_model=OkResponse, tags=[_TAG])
async def do_reset(
    data: VolunteerResetPassword,
    session: AsyncSession = Depends(get_db),
):
    """Сброс пароля по токену из письма. Невалид/протух → 400 INVALID_TOKEN."""
    await reset_password(session, data.token, data.new_password)
    await session.commit()
    return OkResponse(ok=True)


@router.patch("/onboarding", response_model=VolunteerProfile, tags=[_TAG])
async def onboarding(
    data: VolunteerOnboarding,
    session: AsyncSession = Depends(get_db),
    current_volunteer: Volunteer = Depends(get_current_volunteer),
):
    """Онбординг: проставить телефон текущего волонтёра."""
    volunteer = await complete_onboarding(session, current_volunteer, data.phone)
    await session.commit()
    return VolunteerProfile.model_validate(volunteer)


@router.get("/me", response_model=VolunteerProfile, tags=[_TAG])
async def me(current_volunteer: Volunteer = Depends(get_current_volunteer)):
    """Профиль текущего волонтёра."""
    return VolunteerProfile.model_validate(current_volunteer)


@router.get("/reports", response_model=Paginated[IncidentListItem], tags=[_TAG])
async def my_reports(
    page: int = 1,
    page_size: int = 50,
    session: AsyncSession = Depends(get_db),
    current_volunteer: Volunteer = Depends(get_current_volunteer),
):
    """Мои отчёты: инциденты, созданные этим волонтёром из приложения, со статусом.

    Свежие первыми (created_at DESC). Только «мои» (Incident.volunteer_id == id
    волонтёра) — аноним/веб/Макс/старые сюда не попадают. Пагинация: page ≥ 1,
    page_size в [1..200].
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    return await incident_service.list_by_volunteer(
        session, current_volunteer.id, page=page, page_size=page_size
    )


@router.get("/mno", response_model=Paginated[MnoDetail], tags=[_TAG])
async def my_mno(
    page: int = 1,
    page_size: int = 50,
    session: AsyncSession = Depends(get_db),
    current_volunteer: Volunteer = Depends(get_current_volunteer),
):
    """Мои МНО: площадки, добавленные этим волонтёром из приложения.

    Свежие первыми (created_at DESC). Только «мои» (Mno.volunteer_id == id волонтёра) —
    ФГИС/ручные/старые сюда не попадают. Пагинация: page ≥ 1, page_size в [1..200].
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    return await mno_service.list_by_volunteer(
        session, current_volunteer.id, page=page, page_size=page_size
    )
