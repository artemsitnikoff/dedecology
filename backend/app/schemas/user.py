from pydantic import BaseModel, EmailStr, Field
from typing import Literal
from uuid import UUID

from .base import ORMBase


class UserShort(ORMBase):
    id: UUID
    fio: str
    email: str
    role: Literal["admin", "user"]


class UserListItem(ORMBase):
    """Строка списка пользователей в Настройках."""
    id: UUID
    fio: str
    email: str
    role: Literal["admin", "user"]
    status: Literal["active", "invited"]


class UserCreate(BaseModel):
    fio: str
    email: EmailStr
    role: Literal["admin", "user"] = "user"


class UserCreateResult(UserShort):
    """Ответ POST /users — выдаёт сгенерированный временный пароль один раз.
    Письмо НЕ отправляется (честно подписываем на фронте)."""
    status: Literal["active", "invited"] = "invited"
    temp_password: str


class ProfileUpdate(BaseModel):
    fio: str


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)
