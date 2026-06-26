from pydantic import BaseModel, EmailStr, Field
from typing import Literal
from uuid import UUID

from .base import ORMBase


class UserShort(ORMBase):
    id: UUID
    fio: str
    email: str
    role: Literal["admin", "user"]
    is_superadmin: bool


class UserListItem(ORMBase):
    """Строка списка пользователей в Настройках."""
    id: UUID
    fio: str
    email: str
    role: Literal["admin", "user"]
    status: Literal["active", "invited"]
    is_superadmin: bool


class UserCreate(BaseModel):
    """Создание пользователя админом: пароль задаётся вручную (инвайт-флоу убран)."""
    fio: str
    email: EmailStr
    role: Literal["admin", "user"] = "user"
    password: str = Field(min_length=6, max_length=128)


class ProfileUpdate(BaseModel):
    fio: str


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)
