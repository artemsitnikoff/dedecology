"""Эндпоинты волонтёра (мобильное приложение), prefix /volunteer.

БЕЗ admin-гейта — это публичный/самообслуживаемый контур волонтёра: регистрация,
подтверждение почты, вход, восстановление пароля, онбординг и профиль. Тонкий слой:
валидация схемой → сервис/токены/mailer → схема ответа.

Письма — через плагинный mailer. Если письмо НЕ ушло (SMTP не настроен → deliver_email
вернул False), токен/ссылку кладём в ОТВЕТ (email_sent=false), чтобы поток можно было
завершить (тест/интеграция). Если ушло (True) — токен в ответ НЕ кладём.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...database import get_db
from ...deps import get_current_volunteer
from ...models import Volunteer
from ...core.security import create_purpose_token, create_volunteer_access_token
from ...schemas.volunteer import (
    OkResponse,
    VolunteerLogin,
    VolunteerLoginResponse,
    VolunteerOnboarding,
    VolunteerProfile,
    VolunteerRegister,
    VolunteerRegisterResponse,
    VolunteerResetPassword,
    VolunteerResetRequest,
    VolunteerResetRequestResponse,
    VolunteerVerifyEmail,
    VolunteerVerifyResponse,
)
from ...services.mailer import deliver_email
from ...services.volunteer import (
    PURPOSE_RESET_PASSWORD,
    PURPOSE_VERIFY_EMAIL,
    RESET_PASSWORD_TOKEN_TTL,
    VERIFY_EMAIL_TOKEN_TTL,
    authenticate,
    complete_onboarding,
    register,
    request_password_reset,
    reset_password,
    verify_email,
)

router = APIRouter()

_TAG = "Волонтёры (мобильное приложение)"


@router.post("/register", response_model=VolunteerRegisterResponse, status_code=201, tags=[_TAG])
async def register_volunteer(
    data: VolunteerRegister,
    session: AsyncSession = Depends(get_db),
):
    """Регистрация волонтёра. Дубль email → 409. Шлём письмо со ссылкой подтверждения."""
    volunteer = await register(session, data)
    await session.commit()

    token = create_purpose_token(
        str(volunteer.id), PURPOSE_VERIFY_EMAIL, VERIFY_EMAIL_TOKEN_TTL
    )
    verify_url = f"{settings.APP_PUBLIC_URL}/verify?token={token}"
    sent = deliver_email(
        volunteer.email,
        subject="ЭкоПульс — подтверждение адреса почты",
        body="Здравствуйте!\n\n"
        f"Подтвердите адрес электронной почты, перейдя по ссылке:\n{verify_url}\n\n"
        f"Если вы не регистрировались в ЭкоПульс — просто проигнорируйте это письмо.",
    )

    return VolunteerRegisterResponse(
        volunteer_id=volunteer.id,
        email=volunteer.email,
        email_sent=sent,
        email_verify_token=None if sent else token,
        verify_url=None if sent else verify_url,
    )


@router.post("/verify-email", response_model=VolunteerVerifyResponse, tags=[_TAG])
async def verify_volunteer_email(
    data: VolunteerVerifyEmail,
    session: AsyncSession = Depends(get_db),
):
    """Подтверждение почты по токену из письма. Невалид/протух → 400 INVALID_TOKEN."""
    await verify_email(session, data.token)
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

    token = create_purpose_token(
        str(volunteer.id), PURPOSE_RESET_PASSWORD, RESET_PASSWORD_TOKEN_TTL
    )
    reset_url = f"{settings.APP_PUBLIC_URL}/reset?token={token}"
    sent = deliver_email(
        volunteer.email,
        subject="ЭкоПульс — восстановление пароля",
        body="Здравствуйте!\n\n"
        f"Для смены пароля перейдите по ссылке:\n{reset_url}\n\n"
        f"Если вы не запрашивали сброс пароля — просто проигнорируйте это письмо.",
    )

    return VolunteerResetRequestResponse(
        ok=True,
        email_sent=sent,
        reset_token=None if sent else token,
        reset_url=None if sent else reset_url,
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
