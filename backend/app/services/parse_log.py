"""Отдельный файловый лог разбора адреса: промпт + ответ CLI + результат.

Пишется в {STORAGE_DIR}/logs/parse.log (ротация 5МБ × 3), ОТДЕЛЬНО от основного
лога приложения, чтобы оператор мог следить вживую:

  docker compose -f docker-compose.prod.yml exec backend tail -f storage/logs/parse.log

Каждый разбор = блок: ВХОД (текст) → ПРОМПТ → ОТВЕТ CLI → РАЗОБРАНО → ИТОГ (путь+поля).
Сбой записи (нет прав/диска) НЕ роняет разбор — деградируем молча.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ..config import settings

_logger = logging.getLogger("dedecology.parse")
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
            log_dir / "parse.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        _logger.addHandler(handler)
    except Exception:  # noqa: BLE001 — лог не должен ронять разбор
        _logger.addHandler(logging.NullHandler())


def log_ai(text: str, model: str, prompt: str, raw, parsed) -> None:
    """Лог одного AI-разбора: вход, модель, промпт, сырой ответ CLI, распарсенный JSON."""
    _ensure()
    try:
        _logger.info(
            "─── AI-разбор (model=%s) ───\n  ВХОД: %s\n  ПРОМПТ: %s\n  ОТВЕТ CLI: %s\n  РАЗОБРАНО: %s",
            model,
            text,
            prompt,
            raw if raw else "(пусто / CLI недоступен)",
            parsed if parsed is not None else "(JSON не извлечён)",
        )
    except Exception:  # noqa: BLE001
        pass


def log_resolved(
    text: str, path: str, region: str, city: str, street: str, coords: str
) -> None:
    """Лог итога resolve_address: какой путь сработал и финальные поля."""
    _ensure()
    try:
        _logger.info(
            "  ИТОГ [путь=%s]: регион=%r | город=%r | улица=%r | коорд=%r\n",
            path,
            region,
            city,
            street,
            coords,
        )
    except Exception:  # noqa: BLE001
        pass
