"""Бизнес-логика волонтёров (мобильное приложение) — изолирована от admin-users.

Все функции async, session — первым параметром; flush() здесь, commit() — в роутере.
Пароль — тот же хеш, что и у пользователей админки (core.security), но своя таблица
volunteers и свой JWT (typ="volunteer"). Кидаем кастомные AppError-исключения, не
HTTPException. Служебные токены (verify_email / reset_password) — подписанный JWT без
отдельной таблицы; ГЕНЕРАЦИЯ токенов и отправка письма — на уровне роутера (оркестрация).
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import (
    BlockedError,
    ConflictError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
)
from ..core.security import (
    decode_purpose_token,
    get_password_hash,
    verify_password,
)
from ..models import Volunteer
from ..schemas.volunteer import VolunteerRegister

# Время жизни служебных токенов (роутер передаёт их в create_purpose_token).
VERIFY_EMAIL_TOKEN_TTL = timedelta(hours=48)
RESET_PASSWORD_TOKEN_TTL = timedelta(hours=2)

# Назначения служебных токенов.
PURPOSE_VERIFY_EMAIL = "verify_email"
PURPOSE_RESET_PASSWORD = "reset_password"


async def get_by_email(session: AsyncSession, email: str) -> Volunteer | None:
    """Волонтёр по email (без исключения — None, если нет)."""
    result = await session.execute(select(Volunteer).where(Volunteer.email == email))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, vol_id: UUID) -> Volunteer:
    """Волонтёр по id; отсутствует → NotFoundError (404)."""
    result = await session.execute(select(Volunteer).where(Volunteer.id == vol_id))
    volunteer = result.scalar_one_or_none()
    if volunteer is None:
        raise NotFoundError("Волонтёр")
    return volunteer


async def register(session: AsyncSession, data: VolunteerRegister) -> Volunteer:
    """Создаёт волонтёра (email_verified=false, is_active=true). Дубль email → 409.

    После flush() id проставлен БД (gen_random_uuid) — роутер по нему генерит verify-токен.
    """
    if await get_by_email(session, data.email) is not None:
        raise ConflictError("Волонтёр с таким email уже зарегистрирован")

    volunteer = Volunteer(
        email=data.email,
        password_hash=get_password_hash(data.password),
        phone=None,
        email_verified=False,
        is_active=True,
    )
    session.add(volunteer)
    try:
        await session.flush()
    except IntegrityError:
        # Гонка на уникальном email: откат ДО raise, иначе commit в роутере упадёт
        # PendingRollbackError (та же защита, что в services/user.create_user).
        await session.rollback()
        raise ConflictError("Волонтёр с таким email уже зарегистрирован")
    return volunteer


async def verify_email(session: AsyncSession, token: str) -> Volunteer:
    """Подтверждает почту по verify-токену. Битый/протух/чужой purpose → InvalidTokenError."""
    vol_id = decode_purpose_token(token, PURPOSE_VERIFY_EMAIL)
    if vol_id is None:
        raise InvalidTokenError()
    try:
        volunteer = await get_by_id(session, UUID(vol_id))
    except (ValueError, NotFoundError):
        raise InvalidTokenError()

    volunteer.email_verified = True
    await session.flush()
    return volunteer


async def authenticate(session: AsyncSession, email: str, password: str) -> Volunteer:
    """Проверка email+пароля волонтёра.

    - неизвестный email / неверный пароль → InvalidCredentialsError (401);
    - почта не подтверждена → EmailNotVerifiedError (403);
    - заблокирован админом → BlockedError (403).
    Порядок флагов: сперва email_verified, затем is_active (по контракту).
    """
    volunteer = await get_by_email(session, email)
    if volunteer is None or not verify_password(password, volunteer.password_hash):
        raise InvalidCredentialsError()
    if not volunteer.email_verified:
        raise EmailNotVerifiedError()
    if not volunteer.is_active:
        raise BlockedError()
    # Успешный вход — фиксируем момент последней авторизации (commit — в роутере).
    volunteer.last_seen_at = datetime.now(timezone.utc)
    await session.flush()
    return volunteer


async def request_password_reset(session: AsyncSession, email: str) -> Volunteer | None:
    """Возвращает волонтёра по email или None (лёгкая анти-энумерация в роутере).

    Токен сброса и письмо — на уровне роутера (только если волонтёр найден).
    """
    return await get_by_email(session, email)


async def reset_password(session: AsyncSession, token: str, new_password: str) -> Volunteer:
    """Сброс пароля по reset-токену. Битый/протух/чужой purpose → InvalidTokenError."""
    vol_id = decode_purpose_token(token, PURPOSE_RESET_PASSWORD)
    if vol_id is None:
        raise InvalidTokenError()
    try:
        volunteer = await get_by_id(session, UUID(vol_id))
    except (ValueError, NotFoundError):
        raise InvalidTokenError()

    volunteer.password_hash = get_password_hash(new_password)
    await session.flush()
    return volunteer


async def complete_onboarding(
    session: AsyncSession, volunteer: Volunteer, phone: str
) -> Volunteer:
    """Проставляет телефон волонтёра (онбординг после первого входа)."""
    volunteer.phone = phone or None
    await session.flush()
    return volunteer


# --- Админ-справочник ---


async def list_all(session: AsyncSession) -> list[Volunteer]:
    """Все волонтёры, новые сверху (для справочника «Волонтёры» в админке)."""
    result = await session.execute(
        select(Volunteer).order_by(Volunteer.created_at.desc())
    )
    return list(result.scalars().all())


async def set_active(session: AsyncSession, vol_id: UUID, is_active: bool) -> Volunteer:
    """Блокировка/разблокировка волонтёра админом. Нет волонтёра → NotFoundError (404)."""
    volunteer = await get_by_id(session, vol_id)
    volunteer.is_active = is_active
    await session.flush()
    return volunteer


async def delete(session: AsyncSession, vol_id: UUID) -> None:
    """Удаляет волонтёра. Нет волонтёра → NotFoundError (404)."""
    volunteer = await get_by_id(session, vol_id)
    await session.delete(volunteer)
    await session.flush()
