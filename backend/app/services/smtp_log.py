"""Отдельный файловый лог SMTP-отправок: попытка → успех/ошибка (с причиной).

Пишется в {STORAGE_DIR}/logs/smtp.log (ротация 5МБ × 3), ОТДЕЛЬНО от основного
лога приложения, чтобы оператор мог следить вживую за тестовыми письмами и сбоями:

  docker compose -f docker-compose.prod.yml exec backend tail -f storage/logs/smtp.log

Каждая отправка = строка ПОПЫТКА (host/port/шифрование/логин/from/to) → ✓ УСПЕХ
или ✗ ОШИБКА (код + честная причина от сервера). ПАРОЛЬ НИКОГДА не логируется.
Сбой записи (нет прав/диска) НЕ роняет отправку — деградируем молча.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ..config import settings

_logger = logging.getLogger("dedecology.smtp")
_logger.setLevel(logging.INFO)
_logger.propagate = False  # не дублируем эти строки в основной лог приложения

_configured = False


def _ensure() -> None:
    """Лениво вешаем файловый handler один раз. Любой сбой → NullHandler (молчим)."""
    global _configured
    if _configured:
        return
    _configured = True
    try:
        log_dir = Path(settings.STORAGE_DIR) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "smtp.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        _logger.addHandler(handler)
    except Exception:  # noqa: BLE001 — лог не должен ронять отправку
        _logger.addHandler(logging.NullHandler())


def log_attempt(
    *, host: str, port: int, encryption: str, username: str, from_email: str, to: str
) -> None:
    """Лог попытки отправки. ПАРОЛЬ сюда НЕ передаётся и не пишется."""
    _ensure()
    try:
        _logger.info(
            "ПОПЫТКА → %s:%s enc=%s login=%r from=%r to=%r",
            host,
            port,
            encryption,
            username or "(без логина)",
            from_email,
            to,
        )
    except Exception:  # noqa: BLE001
        pass


def log_success(*, host: str, to: str) -> None:
    """Лог успешной отправки (сервер принял письмо без исключения)."""
    _ensure()
    try:
        _logger.info("✓ УСПЕХ  %s → %s", host, to)
    except Exception:  # noqa: BLE001
        pass


def log_failure(*, host: str, to: str, code: str, reason: str) -> None:
    """Лог сбоя: код ошибки (SMTP_AUTH_ERROR и т.п.) + честная причина от сервера."""
    _ensure()
    try:
        _logger.warning("✗ ОШИБКА %s → %s | code=%s | причина: %s", host, to, code, reason)
    except Exception:  # noqa: BLE001
        pass
