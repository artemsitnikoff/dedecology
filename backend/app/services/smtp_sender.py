"""SMTP-транспорт: реальная отправка письма через stdlib smtplib.

Без сторонних зависимостей (aiosmtplib не нужен). Синхронный smtplib крутится
в пуле потоков (asyncio.to_thread), чтобы не блокировать event loop async-эндпоинта.

Все сбои — честные: исключения smtplib/сети маппятся на AppError с понятным
кодом и причиной (status 400), а НЕ проглатываются молча. «Отправлено» = реально
сервер принял письмо без исключения.
"""

import asyncio
import smtplib
import socket
import ssl
from email.message import EmailMessage

from ..core.errors import AppError
from . import smtp_log

# Таймаут на соединение/операции SMTP (сек). Не висим бесконечно на мёртвом хосте.
SMTP_TIMEOUT = 20


def _fail(host: str, to: str, code: str, message: str, e: Exception) -> None:
    """Логирует сбой в smtp.log (код + причина) и бросает AppError. Не возвращает."""
    smtp_log.log_failure(host=host, to=to, code=code, reason=str(e))
    raise AppError(code=code, message=message, status_code=400, details={"reason": str(e)})


def _build_message(
    from_email: str,
    from_name: str,
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    return msg


def _send_sync(
    host: str,
    port: int,
    encryption: str,
    username: str,
    password: str,
    msg: EmailMessage,
) -> None:
    """Синхронная отправка (выполняется в отдельном потоке)."""
    context = ssl.create_default_context()

    if encryption == "ssl":
        with smtplib.SMTP_SSL(host, port, context=context, timeout=SMTP_TIMEOUT) as server:
            if username:
                server.login(username, password)
            server.send_message(msg)
    else:
        # tls (STARTTLS) или none (без шифрования)
        with smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT) as server:
            server.ehlo()
            if encryption == "tls":
                server.starttls(context=context)
                server.ehlo()
            if username:
                server.login(username, password)
            server.send_message(msg)


async def send_via_smtp(
    *,
    host: str,
    port: int,
    encryption: str,
    username: str,
    password: str,
    from_email: str,
    from_name: str,
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
) -> None:
    """Отправляет письмо. Бросает AppError с честным кодом/причиной при сбое.

    Возврат без исключения = сервер принял письмо.
    """
    msg = _build_message(from_email, from_name, to, subject, body_text, body_html)

    # Лог попытки (без пароля) — оператор видит в storage/logs/smtp.log что и куда шлём.
    smtp_log.log_attempt(
        host=host, port=port, encryption=encryption, username=username,
        from_email=from_email, to=to,
    )

    try:
        await asyncio.to_thread(
            _send_sync, host, port, encryption, username, password, msg
        )
    except smtplib.SMTPAuthenticationError as e:
        _fail(host, to, "SMTP_AUTH_ERROR",
              "Не удалось авторизоваться на SMTP-сервере — проверьте логин и пароль", e)
    except smtplib.SMTPConnectError as e:
        _fail(host, to, "SMTP_CONNECT_ERROR", "Не удалось подключиться к SMTP-серверу", e)
    except smtplib.SMTPRecipientsRefused as e:
        _fail(host, to, "SMTP_RECIPIENT_REFUSED", "SMTP-сервер отклонил адрес получателя", e)
    except smtplib.SMTPException as e:
        # Любая прочая SMTP-ошибка (sender refused, data error, disconnect и т.п.)
        _fail(host, to, "SMTP_SEND_ERROR", "Ошибка SMTP при отправке письма", e)
    except ssl.SSLError as e:
        # SSLError — подкласс OSError, ловим до общего OSError
        _fail(host, to, "SMTP_TLS_ERROR",
              "Ошибка TLS/SSL при подключении к SMTP-серверу (проверьте порт и режим шифрования)", e)
    except (socket.timeout, TimeoutError) as e:
        _fail(host, to, "SMTP_TIMEOUT",
              "Таймаут подключения к SMTP-серверу (проверьте хост и порт)", e)
    except (socket.gaierror, ConnectionError, OSError) as e:
        _fail(host, to, "SMTP_CONNECT_ERROR",
              "Не удалось подключиться к SMTP-серверу (проверьте хост и порт)", e)
    else:
        smtp_log.log_success(host=host, to=to)
