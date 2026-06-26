from pydantic import BaseModel, EmailStr
from typing import Literal
from uuid import UUID

from .base import ORMBase


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMe(ORMBase):
    id: UUID
    email: str
    fio: str
    role: Literal["admin", "user"]
    status: Literal["active", "invited"]
    is_superadmin: bool
