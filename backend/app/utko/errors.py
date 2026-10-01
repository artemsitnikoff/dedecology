"""Ошибки УТКО-совместимого API — СВОЙ формат, НЕ общий конверт приложения.

У приложения конверт {error:{code,message,details}} (app/core/errors.py). УТКО-клиент его
НЕ понимает — таблицы проверок в доке задают иные тела и тексты. Поэтому УТКО-эндпоинты
кидают `UtkoError`, а зарегистрированный в app.main хэндлер отдаёт тело в формате УТКО:

  400 → {"success": false, "error": <code>, "errorMessage": <текст>}
  422 → {"errorMessage": <текст>}
  403 → {"errorMessage": "Доступ запрещен"} (или "Отсутствуют полномочия на МНО <id>")
  401 → {"errorMessage": "Unauthorized"}

Тексты сообщений 422/403 берутся ДОСЛОВНО из таблиц доки — см. хелперы ниже.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class UtkoError(Exception):
    """Ошибка УТКО-эндпоинта. Несёт HTTP-статус и готовое тело ответа (dict)."""

    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self.payload = payload
        super().__init__(payload.get("errorMessage", "utko error"))


async def utko_error_handler(request: Request, exc: UtkoError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.payload)


# --- Конструкторы ошибок по таблицам доки ----------------------------------------


def bad_request(error_message: str, error: str = "internal") -> UtkoError:
    """400 Bad Request — тело {success:false, error, errorMessage} (как у /connect/token)."""
    return UtkoError(
        400,
        {"success": False, "error": error, "errorMessage": error_message},
    )


def unprocessable(error_message: str) -> UtkoError:
    """422 Unprocessable Entity — тело {errorMessage} (таблицы проверок)."""
    return UtkoError(422, {"errorMessage": error_message})


def forbidden(error_message: str = "Доступ запрещен") -> UtkoError:
    """403 — тело {errorMessage}. По умолчанию «Доступ запрещен»."""
    return UtkoError(403, {"errorMessage": error_message})


def unauthorized() -> UtkoError:
    """401 Unauthorized — нет/битый/просроченный токен."""
    return UtkoError(401, {"errorMessage": "Unauthorized"})


# --- Готовые тексты проверок (ДОСЛОВНО из доки) ----------------------------------


def missing_attr(name: str) -> UtkoError:
    return unprocessable(f"Отсутствует обязательный атрибут {name}")


def wrong_type(name: str) -> UtkoError:
    return unprocessable(f"Неверный тип данных у атрибута {name}")


def bad_value(name: str) -> UtkoError:
    return unprocessable(f"Свойство {name} имеет недопустимое значение")


def unknown_event() -> UtkoError:
    return unprocessable("Отсутствуют сведения о событии eventId")


def unknown_mno(mno_id: str) -> UtkoError:
    return unprocessable(f"В БД ФГИС УТКО отсутствуют сведения МНО {mno_id}")


def no_mno_authority(mno_id: str) -> UtkoError:
    return forbidden(f"Отсутствуют полномочия на МНО {mno_id}")
