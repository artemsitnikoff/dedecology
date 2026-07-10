"""Бизнес-логика волонтёров (мобильное приложение) — изолирована от admin-users.

Все функции async, session — первым параметром; flush() здесь, commit() — в роутере.
Пароль — тот же хеш, что и у пользователей админки (core.security), но своя таблица
volunteers и свой JWT (typ="volunteer"). Кидаем кастомные AppError-исключения, не
HTTPException. Подтверждение почты — короткий 4-значный код (OTP), хранится в самой
записи volunteer (email_code + срок/попытки/кулдаун), одноразовый. Сброс пароля —
по-прежнему подписанный JWT-токен (reset_password) без отдельной таблицы; reset-письмо
(публичный запрос И админ-триггер) — общий хелпер send_reset_email.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.errors import (
    AppError,
    BlockedError,
    ConflictError,
    EmailDomainBlockedError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
)
from ..core.security import (
    create_purpose_token,
    decode_purpose_token,
    get_password_hash,
    verify_password,
)
from ..models import Incident, Volunteer
from ..schemas.volunteer import VolunteerRegister
from . import blocked_domain as blocked_domain_service
from . import smtp as smtp_service
from .audit import audit
from .smtp_templates import render_simple_email

logger = logging.getLogger(__name__)

# --- Подтверждение почты 4-значным кодом (OTP по письму) ---
EMAIL_CODE_LENGTH = 4  # длина кода (знаков)
EMAIL_CODE_TTL_MINUTES = 15  # срок действия выданного кода
EMAIL_CODE_RESEND_COOLDOWN_SECONDS = 60  # пауза между повторными отправками
EMAIL_CODE_MAX_ATTEMPTS = 5  # неверных попыток → код блокируется, нужен новый

# Время жизни reset-токена (роутер/хелпер передают его в create_purpose_token).
RESET_PASSWORD_TOKEN_TTL = timedelta(hours=2)

# Назначение служебного токена сброса пароля.
PURPOSE_RESET_PASSWORD = "reset_password"


def _issue_email_code(volunteer: Volunteer) -> str:
    """Выдаёт волонтёру новый 4-значный код подтверждения почты (мутирует запись).

    Код генерируется криптостойко (secrets), с ведущими нулями (напр. "0472").
    Сбрасывает срок действия (utcnow + TTL), момент отправки (для кулдауна) и счётчик
    неверных попыток. Возвращает сам код — вызывающий кладёт его в письмо/ответ.
    """
    code = f"{secrets.randbelow(10 ** EMAIL_CODE_LENGTH):0{EMAIL_CODE_LENGTH}d}"
    now = datetime.now(timezone.utc)
    volunteer.email_code = code
    volunteer.email_code_expires_at = now + timedelta(minutes=EMAIL_CODE_TTL_MINUTES)
    volunteer.email_code_sent_at = now
    volunteer.email_code_attempts = 0
    return code


async def _try_send(
    session: AsyncSession,
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> bool:
    """Шлёт письмо через настроенный UI-SMTP; НИКОГДА не роняет вызывающий флоу.

    Возвращает честный bool (как раньше deliver_email): True — письмо ушло; False — SMTP
    не настроен (ValidationError) или отправка упала (AppError и пр.). При любом исключении
    логируем и возвращаем False — тогда вызывающий кладёт код/ссылку в ОТВЕТ (без фейка
    «письмо ушло»), пользователь не заперт.
    """
    try:
        await smtp_service.send_email(
            session, to=to, subject=subject, body_text=body_text, body_html=body_html
        )
        return True
    except Exception:  # noqa: BLE001 — SMTP не настроен/сбой не должен ронять эндпоинт
        logger.warning(
            "email not sent (SMTP не настроен или сбой): to=%s subject=%r", to, subject
        )
        return False


async def send_email_code(session: AsyncSession, volunteer: Volunteer) -> bool:
    """Выдаёт новый код подтверждения (см. _issue_email_code) и шлёт его письмом.

    ЕДИНЫЙ путь для регистрации и повторной отправки (resend) — логика кода/письма не
    дублируется. Письмо уходит через настроенный UI-SMTP (Настройки → Почта). Возвращает
    email_sent: _try_send честно вернёт False, если SMTP не настроен (или отправка упала) —
    тогда вызывающий кладёт код в ОТВЕТ (без фейка «письмо ушло»), а сам код уже проставлен
    в volunteer.email_code.
    """
    code = _issue_email_code(volunteer)
    body_text = (
        "Здравствуйте!\n\n"
        f"Ваш код подтверждения адреса почты в ЭкоПульс: {code}\n\n"
        f"Код действует {EMAIL_CODE_TTL_MINUTES} минут. "
        f"Если вы не регистрировались в ЭкоПульс — просто проигнорируйте это письмо."
    )
    # code — только цифры (0..9), экранировать не нужно.
    body_html = render_simple_email(
        "Код подтверждения",
        "<p style=\"margin:0 0 12px;\">Ваш код подтверждения адреса почты в "
        "<strong style=\"color:#1F9D57;\">«ЭкоПульс»</strong>:</p>"
        "<p style=\"margin:0 0 12px;font-size:28px;font-weight:700;letter-spacing:4px;"
        f"color:#0F1620;\">{code}</p>"
        f"<p style=\"margin:0;\">Код действует {EMAIL_CODE_TTL_MINUTES} минут. "
        "Если вы не регистрировались в ЭкоПульс — просто проигнорируйте это письмо.</p>",
        preheader="Код подтверждения ЭкоПульс",
    )
    return await _try_send(
        session,
        volunteer.email,
        "ЭкоПульс · код подтверждения",
        body_text,
        body_html,
    )


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
    """Создаёт волонтёра (email_verified=false, is_active=true).

    Пароль ≠ повтор → 400 PASSWORDS_MISMATCH; дубль email → 409. После flush() id
    проставлен БД (gen_random_uuid); код подтверждения выдаёт/шлёт роутер (send_email_code).
    """
    if await blocked_domain_service.is_email_blocked(session, data.email):
        domain = data.email.rsplit("@", 1)[-1].strip().lower()
        raise EmailDomainBlockedError(domain)
    if data.password != data.repeat_password:
        raise AppError("PASSWORDS_MISMATCH", "Пароли не совпадают", 400)
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


async def verify_email(session: AsyncSession, email: str, code: str) -> Volunteer:
    """Подтверждает почту волонтёра по 4-значному коду из письма.

    - уже подтверждён → идемпотентно возвращаем волонтёра (без ошибки);
    - нет кода / срок вышел / нет такого email → 400 CODE_EXPIRED (просим новый код);
    - превышен лимит неверных попыток → 429 TOO_MANY_ATTEMPTS (код заблокирован);
    - код не совпал → инкремент попыток (commit, антибрутфорс) → 400 INVALID_CODE
      с details.attempts_left;
    - совпал → email_verified=true, код обнуляется (одноразовый).
    """
    volunteer = await get_by_email(session, email)
    # Идемпотентность: почта уже подтверждена — код больше не нужен.
    if volunteer is not None and volunteer.email_verified:
        return volunteer

    now = datetime.now(timezone.utc)
    # Нет волонтёра/кода или срок вышел → единый ответ «запросите новый код»
    # (заодно анти-энумерация: неизвестный email не отличить от истёкшего кода).
    if (
        volunteer is None
        or not volunteer.email_code
        or volunteer.email_code_expires_at is None
        or volunteer.email_code_expires_at < now
    ):
        raise AppError("CODE_EXPIRED", "Код истёк, запросите новый", 400)

    # Код заблокирован превышением попыток — только новый код разблокирует.
    if volunteer.email_code_attempts >= EMAIL_CODE_MAX_ATTEMPTS:
        raise AppError(
            "TOO_MANY_ATTEMPTS", "Слишком много попыток, запросите новый код", 429
        )

    # Неверный код: инкремент счётчика ДОЛЖЕН пережить raise (роутер до commit не дойдёт),
    # поэтому здесь исключение из правила «commit в роутере» — коммитим сами.
    if code != volunteer.email_code:
        volunteer.email_code_attempts += 1
        await session.commit()
        attempts_left = max(0, EMAIL_CODE_MAX_ATTEMPTS - volunteer.email_code_attempts)
        raise AppError(
            "INVALID_CODE", "Неверный код", 400, details={"attempts_left": attempts_left}
        )

    # Успех — почта подтверждена, код одноразовый (обнуляем всё сопутствующее).
    volunteer.email_verified = True
    volunteer.email_code = None
    volunteer.email_code_expires_at = None
    volunteer.email_code_sent_at = None
    volunteer.email_code_attempts = 0
    await session.flush()
    return volunteer


async def resend_email_code(
    session: AsyncSession, email: str
) -> tuple[bool, bool, Volunteer | None]:
    """Повторно высылает код подтверждения почты. Возвращает (email_sent, already_verified, volunteer).

    - неизвестный email → (False, False, None): анти-энумерация, «успех» без кода;
    - уже подтверждён → (False, True, volunteer): слать нечего;
    - кулдаун ещё не прошёл → 429 RESEND_TOO_SOON с details.resend_after (сек до отправки);
    - иначе → выдаём+шлём новый код (send_email_code), (email_sent, False, volunteer).
    """
    volunteer = await get_by_email(session, email)
    if volunteer is None:
        return False, False, None
    if volunteer.email_verified:
        return False, True, volunteer

    # Кулдаун повторной отправки — защита от спама письмами.
    if volunteer.email_code_sent_at is not None:
        elapsed = (
            datetime.now(timezone.utc) - volunteer.email_code_sent_at
        ).total_seconds()
        if elapsed < EMAIL_CODE_RESEND_COOLDOWN_SECONDS:
            resend_after = EMAIL_CODE_RESEND_COOLDOWN_SECONDS - int(elapsed)
            raise AppError(
                "RESEND_TOO_SOON",
                "Повторная отправка будет доступна позже",
                429,
                details={"resend_after": resend_after},
            )

    email_sent = await send_email_code(session, volunteer)
    await session.flush()
    return email_sent, False, volunteer


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

    Само письмо/токен — общий хелпер send_reset_email (роутер зовёт его, только если
    волонтёр найден, чтобы не раскрывать наличие учётки).
    """
    return await get_by_email(session, email)


async def send_reset_email(
    session: AsyncSession, volunteer: Volunteer
) -> tuple[bool, str, str]:
    """Генерит reset-токен волонтёра и шлёт письмо со ссылкой сброса пароля.

    ЕДИНЫЙ код для публичного запроса (/volunteer/password/reset-request) и админ-триггера
    (admin_reset_password) — логика токена/письма не дублируется. Письмо уходит через
    настроенный UI-SMTP (Настройки → Почта). Возвращает (email_sent, token, reset_url).
    _try_send честно вернёт False, если SMTP не настроен (или отправка упала) — тогда
    вызывающий кладёт token/url в ответ, без фейка «письмо ушло».
    """
    token = create_purpose_token(
        str(volunteer.id), PURPOSE_RESET_PASSWORD, RESET_PASSWORD_TOKEN_TTL
    )
    reset_url = f"{settings.APP_PUBLIC_URL}/reset?token={token}"
    body_text = (
        "Здравствуйте!\n\n"
        f"Для смены пароля перейдите по ссылке:\n{reset_url}\n\n"
        f"Если вы не запрашивали сброс пароля — просто проигнорируйте это письмо."
    )
    # reset_url формируется кодом (JWT-токен, URL-safe) — не пользовательский ввод.
    body_html = render_simple_email(
        "Восстановление пароля",
        "<p style=\"margin:0 0 16px;\">Вы запросили смену пароля в "
        "<strong style=\"color:#1F9D57;\">«ЭкоПульс»</strong>. Нажмите кнопку ниже, "
        "чтобы задать новый пароль:</p>"
        f"<p style=\"margin:0 0 16px;\"><a href=\"{reset_url}\" "
        "style=\"display:inline-block;padding:12px 22px;background:#1F9D57;color:#FFFFFF;"
        "text-decoration:none;border-radius:10px;font-weight:600;\">Сменить пароль</a></p>"
        "<p style=\"margin:0 0 6px;\">Если кнопка не работает — откройте ссылку вручную:</p>"
        f"<p style=\"margin:0 0 16px;word-break:break-all;\"><a href=\"{reset_url}\" "
        f"style=\"color:#1F9D57;\">{reset_url}</a></p>"
        "<p style=\"margin:0;\">Если вы не запрашивали сброс пароля — просто "
        "проигнорируйте это письмо.</p>",
        preheader="Восстановление пароля ЭкоПульс",
    )
    email_sent = await _try_send(
        session,
        volunteer.email,
        "ЭкоПульс · сброс пароля",
        body_text,
        body_html,
    )
    return email_sent, token, reset_url


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


async def change_own_password(
    session: AsyncSession, volunteer: Volunteer, new_password: str
) -> None:
    """Смена собственного пароля волонтёром (мобильное приложение, POST /profile/password).

    Пароль приходит плейнтекстом (или уже MD5-хешем от клиента — нам всё равно, bcrypt-им
    как есть, консистентно с login). flush() здесь, commit() — в роутере. Аудит — системный
    (actor_type='system', actor_user_id=None: действующего пользователя админки нет), как
    у прочих волонтёрских действий."""
    volunteer.password_hash = get_password_hash(new_password)
    await session.flush()
    await audit(
        session,
        action="password_reset",
        entity_type="volunteer",
        entity_id=volunteer.id,
        actor_user_id=None,
        actor_type="system",
    )


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


async def incidents_counts_map(session: AsyncSession, volunteer_ids) -> dict[UUID, int]:
    """{volunteer_id: кол-во обращений} для непустых id — одним GROUP BY.

    Питает колонку «Обращений» в справочнике «Волонтёры». Пустой список id → {}.
    """
    uniq = {vid for vid in volunteer_ids if vid}
    if not uniq:
        return {}
    result = await session.execute(
        select(Incident.volunteer_id, func.count(Incident.id))
        .where(Incident.volunteer_id.in_(uniq))
        .group_by(Incident.volunteer_id)
    )
    return {vid: cnt for vid, cnt in result.all()}


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


async def admin_reset_password(
    session: AsyncSession, vol_id: UUID
) -> tuple[str, bool, str, str]:
    """Админ-триггер сброса пароля волонтёра ПО ID (кнопка в справочнике «Волонтёры»).

    Находит волонтёра (нет → NotFoundError 404); генерит reset-токен и шлёт письмо со
    ссылкой ТЕМ ЖЕ способом, что публичный запрос сброса (общий send_reset_email). БЕЗ
    анти-энумерации — админ знает, кому сбрасывает. Прямой смены пароля здесь НЕТ, БД не
    меняется (только письмо) — commit не нужен. Возвращает (email, email_sent, token,
    reset_url): email нужен роутеру для ответа/тоста, т.к. на входе лишь id.
    """
    volunteer = await get_by_id(session, vol_id)
    email_sent, token, reset_url = await send_reset_email(session, volunteer)
    return volunteer.email, email_sent, token, reset_url
