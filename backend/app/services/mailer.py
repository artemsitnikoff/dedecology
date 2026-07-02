"""Плагинный отправитель писем.

Единая точка отправки почты в приложении. РЕАЛЬНОГО SMTP пока нет, поэтому:
  - SMTP_HOST/SMTP_FROM заданы в настройках → шлём письмо через smtplib, возвращаем True;
  - иначе → логируем «email not sent (SMTP не настроен)» и возвращаем False.

Никаких фейков «письмо отправлено»: возвращаемое значение честно отражает факт отправки.
Вызывающий (регистрация/сброс пароля) по False кладёт токен/ссылку в ОТВЕТ, по True — нет.
"""

import logging
import smtplib
from email.message import EmailMessage

from ..config import settings

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    """SMTP считаем настроенным, если задан хост и адрес отправителя."""
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def deliver_email(to: str, subject: str, body: str) -> bool:
    """Отправляет письмо. True — реально отправлено, False — SMTP не настроен/ошибка.

    Ошибка отправки при настроенном SMTP тоже даёт False (честно: письмо не ушло),
    чтобы вызывающий смог отдать токен/ссылку в ответе и не оставить пользователя без входа.
    """
    if not _smtp_configured():
        logger.warning(
            "email not sent (SMTP не настроен): to=%s subject=%r", to, subject
        )
        return False

    try:
        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        port = settings.SMTP_PORT or 587
        with smtplib.SMTP(settings.SMTP_HOST, port, timeout=15) as smtp:
            smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)

        logger.info("email sent: to=%s subject=%r", to, subject)
        return True
    except Exception:  # noqa: BLE001 — сбой SMTP не должен ронять эндпоинт
        logger.exception("email delivery failed: to=%s", to)
        return False
