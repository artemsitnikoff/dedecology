import logging
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
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


class InvalidCredentialsError(AppError):
    def __init__(self):
        super().__init__(
            code="INVALID_CREDENTIALS",
            message="Неверный email или пароль",
            status_code=401,
        )


class UserInactiveError(AppError):
    def __init__(self):
        super().__init__(
            code="USER_INACTIVE",
            message="Пользователь заблокирован",
            status_code=403,
        )


class AccountLockedError(AppError):
    def __init__(self, minutes_left: int = 0):
        if minutes_left > 0:
            message = f"Слишком много неудачных попыток входа. Попробуйте через {minutes_left} мин."
        else:
            message = "Слишком много неудачных попыток входа. Повторите позже."
        super().__init__(
            code="ACCOUNT_LOCKED",
            message=message,
            status_code=429,
        )


class NotFoundError(AppError):
    def __init__(self, entity: str = "Объект"):
        super().__init__(
            code="NOT_FOUND",
            message=f"{entity} не найден",
            status_code=404,
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "Недостаточно прав"):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=403,
        )


class ValidationError(AppError):
    def __init__(self, message: str = "Ошибка валидации", details: dict | list | None = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=400,
            details=details,
        )


class ConflictError(AppError):
    def __init__(self, message: str = "Конфликт данных", details: dict | list | None = None, code: str = "CONFLICT"):
        super().__init__(
            code=code,
            message=message,
            status_code=409,
            details=details,
        )


class InvalidTokenError(AppError):
    """Битая/просроченная ссылка подтверждения почты или сброса пароля (волонтёр)."""

    def __init__(self, message: str = "Ссылка недействительна или устарела"):
        super().__init__(
            code="INVALID_TOKEN",
            message=message,
            status_code=400,
        )


class EmailNotVerifiedError(AppError):
    """Волонтёр не подтвердил почту — вход запрещён (403)."""

    def __init__(self):
        super().__init__(
            code="EMAIL_NOT_VERIFIED",
            message="Подтвердите адрес электронной почты, чтобы войти",
            status_code=403,
        )


class BlockedError(AppError):
    """Учётка волонтёра заблокирована администратором (403)."""

    def __init__(self):
        super().__init__(
            code="BLOCKED",
            message="Учётная запись заблокирована",
            status_code=403,
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        field = ".".join(str(x) for x in error["loc"]) if error["loc"] else "root"
        details.append({
            "field": field,
            "message": error["msg"],
        })

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Ошибка валидации данных",
                "details": details,
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException | StarletteHTTPException) -> JSONResponse:
    """Convert FastAPI/Starlette HTTPException to unified error format"""
    code_mapping = {
        401: "NOT_AUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        422: "VALIDATION_ERROR",
        500: "INTERNAL_ERROR",
    }

    error_code = code_mapping.get(exc.status_code, "HTTP_ERROR")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code,
                "message": str(exc.detail),
                "details": None,
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions with unified error format and logging"""
    logger.exception("Unhandled exception", exc_info=exc)

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Внутренняя ошибка сервера",
                "details": None,
            }
        },
    )
