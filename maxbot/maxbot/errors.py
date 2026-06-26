"""Доменные исключения maxbot.

Сервисы (например, intake_client) поднимают AppError, а не HTTPException —
это не FastAPI-приложение, а long-polling воркер. Обработчик сообщения ловит
AppError, логирует и отвечает пользователю мягким сообщением, не роняя поллер.
"""

from __future__ import annotations


class AppError(Exception):
    """Базовая ошибка приложения с машинным кодом и человекочитаемым текстом."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | list | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class IntakeError(AppError):
    """Backend intake API вернул не-2xx или оказался недоступен."""

    def __init__(self, message: str, status_code: int = 502, details: dict | list | None = None):
        super().__init__(
            code="INTAKE_ERROR",
            message=message,
            status_code=status_code,
            details=details,
        )
