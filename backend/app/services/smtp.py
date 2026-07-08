"""SMTP-интеграция (бизнес-логика, single-tenant — БЕЗ company_id).

Конфиг хранится в типизированной таблице `smtp_settings` — ЕДИНСТВЕННАЯ строка на
арендатора (get-or-create). Пароль шифруется Fernet (`password_enc`) и НИКОГДА не
возвращается наружу. `status='connected'` выставляется только после УСПЕШНОЙ
тестовой отправки.

`send_email()` — переиспользуемое ядро отправки (для будущих оповещений по событиям).
"""

from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SmtpSettings
from ..core.crypto import encrypt_text, decrypt_text
from ..core.errors import ValidationError
from .audit import audit
from .smtp_sender import send_via_smtp
from .smtp_templates import render_simple_email

ENCRYPTION_MODES = ("tls", "ssl", "none")


def _is_valid_email(value: str) -> bool:
    """Лёгкая проверка email (полную валидацию даёт схема/email-validator)."""
    if not value or "@" not in value:
        return False
    local, _, domain = value.partition("@")
    return bool(local) and "." in domain


async def _get(session: AsyncSession) -> Optional[SmtpSettings]:
    """Единственная строка настроек SMTP (или None, если ещё не сохраняли)."""
    result = await session.execute(select(SmtpSettings).limit(1))
    return result.scalar_one_or_none()


async def get_status(session: AsyncSession) -> dict:
    """Статус SMTP-интеграции. Пароль НИКОГДА не отдаётся."""
    row = await _get(session)
    if not row or not row.host:
        return {
            "configured": False,
            "verified": False,
            "host": None,
            "port": None,
            "encryption": None,
            "username": None,
            "from_email": None,
            "from_name": None,
            "last_test_at": None,
            "last_test_ok": False,
            "last_test_error": None,
        }

    return {
        "configured": True,
        "verified": row.status == "connected" and bool(row.last_test_ok),
        "host": row.host,
        "port": row.port,
        "encryption": row.encryption,
        "username": row.username or None,
        "from_email": row.from_email,
        "from_name": row.from_name or None,
        "last_test_at": row.last_test_at.isoformat() if row.last_test_at else None,
        "last_test_ok": bool(row.last_test_ok),
        "last_test_error": row.last_test_error,
    }


async def save_config(
    session: AsyncSession,
    actor_user_id: UUID,
    *,
    host: str,
    port: int,
    encryption: str,
    username: str,
    password: str,
    from_email: str,
    from_name: str,
) -> SmtpSettings:
    """Сохраняет/обновляет SMTP-конфиг (единственная строка, get-or-create).

    Пароль write-only: пустой ввод при уже существующей конфигурации → старый
    пароль сохраняется (наружу целиком не отдаётся); пусто и старого нет →
    ValidationError. Любое сохранение сбрасывает verified (проверить тестом заново).
    Делает flush (commit — в роутере).
    """
    host = (host or "").strip()
    if not host:
        raise ValidationError("Укажите SMTP-сервер (host)")
    if not isinstance(port, int) or isinstance(port, bool) or not (1 <= port <= 65535):
        raise ValidationError("Порт должен быть числом от 1 до 65535")
    if encryption not in ENCRYPTION_MODES:
        raise ValidationError("Шифрование должно быть одним из: tls, ssl, none")

    from_email = (from_email or "").strip()
    if not _is_valid_email(from_email):
        raise ValidationError("Укажите корректный email отправителя")

    username = (username or "").strip()
    from_name = (from_name or "").strip()

    row = await _get(session)

    # Мердж пароля (write-only).
    if password:
        password_enc = encrypt_text(password)
    else:
        password_enc = row.password_enc if row else ""
    if not password_enc:
        raise ValidationError("Укажите пароль SMTP")

    if row is None:
        row = SmtpSettings()
        session.add(row)

    row.host = host
    row.port = port
    row.encryption = encryption
    row.username = username
    row.password_enc = password_enc
    row.from_email = from_email
    row.from_name = from_name
    # Любая смена конфигурации сбрасывает статус проверки.
    row.status = "disconnected"
    row.last_test_at = None
    row.last_test_ok = False
    row.last_test_error = None

    await session.flush()

    await audit(
        session,
        action="smtp_config_saved",
        entity_type="smtp_settings",
        entity_id=row.id,
        after={
            "host": host,
            "port": port,
            "encryption": encryption,
            "from_email": from_email,
        },
        actor_user_id=actor_user_id,
    )

    return row


async def send_email(
    session: AsyncSession,
    *,
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> None:
    """Переиспользуемое ядро отправки письма через настроенный SMTP.

    Бросает ValidationError, если SMTP не настроен; AppError при сбое отправки.
    """
    row = await _get(session)
    if not row or not row.host:
        raise ValidationError("SMTP не настроен — сохраните настройки почтового сервера")

    password = decrypt_text(row.password_enc) if row.password_enc else ""

    await send_via_smtp(
        host=row.host,
        port=int(row.port),
        encryption=row.encryption or "ssl",
        username=row.username or "",
        password=password,
        from_email=row.from_email,
        from_name=row.from_name or "",
        to=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )


async def send_test_email(
    session: AsyncSession,
    actor_user_id: UUID,
    *,
    to: str,
) -> dict:
    """Отправляет тестовое письмо и фиксирует результат в last_test_*.

    Коммитит САМ (на обоих путях), чтобы метаданные теста — в т.ч. ошибка —
    сохранились даже при сбое отправки (роутер на ошибке не коммитит).
    """
    to = (to or "").strip()
    if not _is_valid_email(to):
        raise ValidationError("Укажите корректный email получателя теста")

    row = await _get(session)
    if not row or not row.host:
        raise ValidationError("SMTP не настроен — сначала сохраните настройки")

    subject = "ЭкоПульс · тестовое письмо"
    body_text = (
        "Это тестовое письмо от системы «ЭкоПульс».\n\n"
        "Если вы его получили — настройки SMTP корректны, и ЭкоПульс сможет "
        "отправлять уведомления через ваш почтовый сервер."
    )
    body_html = render_simple_email(
        "Тестовое письмо",
        "<p style=\"margin:0 0 12px;\">Это тестовое письмо от системы "
        "<strong style=\"color:#1F9D57;\">«ЭкоПульс»</strong> 💚.</p>"
        "<p style=\"margin:0;\">Если вы его получили — настройки SMTP корректны, и "
        "ЭкоПульс сможет отправлять уведомления через ваш почтовый сервер.</p>",
        preheader="Тестовое письмо от ЭкоПульс",
    )

    now = datetime.now(timezone.utc)

    try:
        await send_email(
            session,
            to=to,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
    except Exception as e:
        # Фиксируем неуспех (с честной причиной) и пробрасываем.
        row.last_test_at = now
        row.last_test_ok = False
        row.last_test_error = getattr(e, "message", None) or str(e)
        row.status = "disconnected"
        await session.flush()
        await audit(
            session,
            action="smtp_test_failed",
            entity_type="smtp_settings",
            entity_id=row.id,
            after={"to": to, "error": row.last_test_error},
            actor_user_id=actor_user_id,
        )
        await session.commit()
        raise

    # Успех.
    row.last_test_at = now
    row.last_test_ok = True
    row.last_test_error = None
    row.status = "connected"
    await session.flush()
    await audit(
        session,
        action="smtp_test_sent",
        entity_type="smtp_settings",
        entity_id=row.id,
        after={"to": to},
        actor_user_id=actor_user_id,
    )
    await session.commit()

    return {"sent_to": to, "last_test_at": now.isoformat()}


async def disconnect(session: AsyncSession, actor_user_id: UUID) -> None:
    """Отключает SMTP: status='disconnected', verified сбрасывается. Конфиг оставляем.

    Делает flush (commit — в роутере).
    """
    row = await _get(session)
    if not row or not row.host:
        raise ValidationError("SMTP не настроен")

    row.status = "disconnected"
    row.last_test_ok = False

    await session.flush()
    await audit(
        session,
        action="smtp_disconnected",
        entity_type="smtp_settings",
        entity_id=row.id,
        actor_user_id=actor_user_id,
    )
