from datetime import datetime, timedelta, timezone
from typing import Union

import bcrypt as _bcrypt
from jose import jwt
from passlib.context import CryptContext

from ..config import settings

# passlib 1.7.4 expects bcrypt.__about__.__version__; bcrypt 4+ exposes __version__ directly.
# Шим оставляем как «пояс и подтяжки» даже при пине bcrypt<4.
if not hasattr(_bcrypt, "__about__"):
    class _About:
        __version__ = _bcrypt.__version__
    _bcrypt.__about__ = _About()  # type: ignore[attr-defined]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    to_encode.update({"type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire})
    to_encode.update({"type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def decode_token(token: str) -> dict:
    """Decode JWT token and return payload"""
    from jose.exceptions import JWTError
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise ValueError("Invalid token")


# ---------------------------------------------------------------------------
# Волонтёры (мобильное приложение) — ОТДЕЛЬНЫЕ токены, изолированы от admin-auth.
#
# Логин-токен волонтёра: claims {sub: vol_id, typ: "volunteer", exp}. Ключ "typ"
# (не "type") с уникальным значением: get_current_user проверяет payload["type"]=="access"
# → волонтёрский токен отбраковывается; get_current_volunteer проверяет payload["typ"]==
# "volunteer" → admin-токен (там "type", а не "typ") отбраковывается. Плюс sub волонтёра —
# UUID из volunteers, которого нет в users, и наоборот. Двойная изоляция.
#
# Токены подтверждения почты / сброса пароля — БЕЗ отдельной таблицы: подписанный JWT с
# claims {sub: vol_id, purpose: "verify_email"|"reset_password", exp}. Одноразовость через
# смену состояния (email_verified/password_hash), не через хранилище токенов.
# ---------------------------------------------------------------------------

# Время жизни логин-токена волонтёра (мобильное приложение — долгоживущий).
VOLUNTEER_ACCESS_TOKEN_EXPIRE_DAYS = 30


def create_volunteer_access_token(vol_id: str, expires_delta: Union[timedelta, None] = None) -> str:
    """Логин-JWT волонтёра: {sub: vol_id, typ: "volunteer", exp}."""
    if expires_delta is None:
        expires_delta = timedelta(days=VOLUNTEER_ACCESS_TOKEN_EXPIRE_DAYS)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"sub": str(vol_id), "typ": "volunteer", "exp": expire}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_purpose_token(vol_id: str, purpose: str, expires: timedelta) -> str:
    """Подписанный служебный токен волонтёра: {sub, purpose, exp}.

    purpose ∈ {"verify_email", "reset_password"}. exp обязателен (передаётся вызывающим).
    """
    expire = datetime.now(timezone.utc) + expires
    to_encode = {"sub": str(vol_id), "purpose": purpose, "exp": expire}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_purpose_token(token: str, purpose: str) -> str | None:
    """Проверяет подпись+exp+совпадение purpose. Возвращает vol_id (str) или None.

    None — на любую ошибку: битый/просроченный токен, неверная подпись, чужой purpose,
    отсутствие sub. Вызывающий трактует None как 400 (ссылка недействительна/устарела).
    """
    from jose.exceptions import JWTError
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("purpose") != purpose:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    return sub
