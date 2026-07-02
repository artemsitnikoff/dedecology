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
    fio: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class VolunteerVerifyEmail(BaseModel):
    token: str = Field(min_length=1)


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
    fio: str
    email: str
    phone: str | None
    email_verified: bool


class VolunteerRegisterResponse(BaseModel):
    volunteer_id: UUID
    email: str
    email_sent: bool
    # Токен/ссылка возвращаются ТОЛЬКО когда письмо не ушло (email_sent=false) —
    # чтобы фронт/тесты смогли завершить подтверждение почты без реального письма.
    email_verify_token: str | None = None
    verify_url: str | None = None


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


class VolunteerListItem(ORMBase):
    """Строка справочника «Волонтёры» в админке."""

    id: UUID
    fio: str
    email: str
    phone: str | None
    email_verified: bool
    is_active: bool
    created_at: datetime
