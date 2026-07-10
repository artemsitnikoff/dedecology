"""Справочник «Стоп-лист почтовых доменов»: CRUD над blocked_email_domains
+ проверка блокировки адреса.

Домен хранится нормализованным (нижний регистр, без ведущего "@"/пробелов). На него
опирается регистрация волонтёра (services/volunteer.register → is_email_blocked): адрес
на заблокированном домене к регистрации не допускается. Все функции async, session —
первым параметром; flush() здесь, commit() — в роутере. Ошибки — AppError-исключения
(ConflictError/NotFoundError/ValidationError), не HTTPException.
"""

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..models import BlockedEmailDomain

_DOMAIN_MAX = 255


def _normalize(domain: str) -> str:
    """Нормализует домен: strip, lower, убирает пробелы и ведущий "@".

    Если передали целый email (есть "@") — берём часть после последнего "@".
    """
    domain = (domain or "").strip().lower()
    if "@" in domain:
        domain = domain.rsplit("@", 1)[-1]
    # Убираем любые пробелы (в т.ч. внутренние) и оставшийся ведущий "@".
    domain = domain.replace(" ", "").lstrip("@")
    return domain


async def list_domains(session: AsyncSession) -> list[BlockedEmailDomain]:
    """Все домены стоп-листа, упорядоченные по имени домена."""
    result = await session.execute(
        select(BlockedEmailDomain).order_by(BlockedEmailDomain.domain)
    )
    return list(result.scalars().all())


async def get_domain(session: AsyncSession, domain_id) -> BlockedEmailDomain:
    """Домен по id; отсутствует → NotFoundError (404)."""
    result = await session.execute(
        select(BlockedEmailDomain).where(BlockedEmailDomain.id == domain_id)
    )
    domain = result.scalar_one_or_none()
    if domain is None:
        raise NotFoundError("Домен")
    return domain


async def create_domain(session: AsyncSession, domain: str) -> BlockedEmailDomain:
    """Добавляет домен в стоп-лист (нормализуя его).

    Пусто ИЛИ без точки → ValidationError (400). Дубль → ConflictError (409).
    Иначе создаёт запись + flush(). Возвращает объект.
    """
    d = _normalize(domain)[:_DOMAIN_MAX]
    if not d or "." not in d:
        raise ValidationError("Укажите корректный домен, напр. gmail.com")

    result = await session.execute(
        select(BlockedEmailDomain.id).where(BlockedEmailDomain.domain == d)
    )
    if result.scalar_one_or_none() is not None:
        raise ConflictError(f"Домен «{d}» уже в стоп-листе")

    blocked = BlockedEmailDomain(domain=d)
    session.add(blocked)
    await session.flush()
    return blocked


async def delete_domain(session: AsyncSession, domain_id) -> None:
    """Удаляет домен из стоп-листа. Не найден → NotFoundError (404)."""
    blocked = await get_domain(session, domain_id)
    await session.delete(blocked)
    await session.flush()


async def is_email_blocked(session: AsyncSession, email: str) -> bool:
    """True, если домен адреса присутствует в стоп-листе.

    Домен = часть после последнего "@" (lower/strip). Пустой → False.
    """
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1].strip()
    if not domain:
        return False
    result = await session.execute(
        select(exists().where(BlockedEmailDomain.domain == domain))
    )
    return bool(result.scalar())
