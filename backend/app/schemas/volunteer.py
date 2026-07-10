"""Схемы волонтёра (мобильное приложение + админ-справочник).

Разделены на запросы (регистрация/логин/верификация/сброс/онбординг/блокировка) и
ответы (профиль, результаты регистрации и сброса, строка админ-списка).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from .base import ORMBase


# --- Запросы (мобильные) ---


class VolunteerRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    # Повтор пароля — сверяется в сервисе (несовпадение → 400 PASSWORDS_MISMATCH).
    repeat_password: str = Field(min_length=6, max_length=128)


class VolunteerVerifyEmail(BaseModel):
    # Подтверждение по 4-значному коду из письма (было — по JWT-токену из ссылки).
    email: EmailStr
    code: str = Field(min_length=1, max_length=8)


class VolunteerResendRequest(BaseModel):
    # Повторная отправка кода подтверждения почты (кулдаун — в сервисе).
    email: EmailStr


class VolunteerLogin(BaseModel):
    email: EmailStr
    password: str


class VolunteerResetRequest(BaseModel):
    email: EmailStr


class VolunteerResetPassword(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


class VolunteerOnboarding(BaseModel):
    # Телефон необязателен по смыслу поля, но онбординг его проставляет; ≤32 символа.
    phone: str = Field(max_length=32)


# --- Запрос (админ) ---


class VolunteerSetActive(BaseModel):
    is_active: bool


# --- Ответы ---


class VolunteerProfile(ORMBase):
    """Профиль волонтёра для мобильного приложения (/me, онбординг, вложен в логин)."""

    id: UUID
    email: str
    phone: str | None
    email_verified: bool


class VolunteerRegisterResponse(BaseModel):
    volunteer_id: UUID
    email: str
    email_sent: bool
    # Длина кода и задержка повторной отправки — константы, отдаём фронту явно.
    code_length: int
    resend_after: int
    # Код возвращается ТОЛЬКО когда письмо не ушло (email_sent=false, SMTP не настроен) —
    # честно, чтобы фронт/тесты смогли завершить подтверждение почты без реального письма.
    email_verify_code: str | None = None


class VolunteerResendResponse(BaseModel):
    ok: bool = True
    email_sent: bool
    # Уже подтверждён → слать нечего (email_sent=false, already_verified=true).
    already_verified: bool = False
    code_length: int
    resend_after: int
    # Код — только при email_sent=false (как в VolunteerRegisterResponse).
    email_verify_code: str | None = None


class VolunteerVerifyResponse(BaseModel):
    ok: bool = True
    email_verified: bool = True


class VolunteerLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    volunteer: VolunteerProfile


class VolunteerResetRequestResponse(BaseModel):
    ok: bool = True
    email_sent: bool
    # Токен/ссылка — только при email_sent=false (см. VolunteerRegisterResponse).
    reset_token: str | None = None
    reset_url: str | None = None


class OkResponse(BaseModel):
    ok: bool = True


class VolunteerAdminResetResult(BaseModel):
    """Результат админ-триггера сброса пароля волонтёра (/volunteers/{id}/reset-password).

    Прямой смены пароля здесь нет — админ лишь инициирует отправку ссылки сброса
    волонтёру. email — почта волонтёра (для тоста «отправлено на …»).
    """

    ok: bool = True
    email: str
    email_sent: bool
    # Токен/ссылка — ТОЛЬКО при email_sent=false (как в VolunteerResetRequestResponse):
    # SMTP не настроен → письмо не ушло, админ видит ссылку и передаёт её волонтёру вручную.
    reset_token: str | None = None
    reset_url: str | None = None


class VolunteerListItem(ORMBase):
    """Строка справочника «Волонтёры» в админке."""

    id: UUID
    email: str
    phone: str | None
    email_verified: bool
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime
    # Кол-во обращений этого волонтёра (source='app'); проставляет роутер из GROUP BY.
    incidents_count: int = 0
