from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.v1.router import api_router
from .config import settings
from .core.errors import (
    AppError,
    app_error_handler,
    validation_error_handler,
    http_exception_handler,
    generic_exception_handler,
)

# Разделы Swagger (`/docs`) — порядок в списке задаёт порядок групп в интерфейсе.
# Русские названия разделов = разделы документации для мобильного приложения.
openapi_tags = [
    {
        "name": "Авторизация",
        "description": "Вход по email+паролю, обновление и отзыв токена, текущий "
        "пользователь. Access-токен — в теле ответа, refresh — в HttpOnly-cookie.",
    },
    {
        "name": "Профиль пользователя",
        "description": "Данные текущего пользователя, смена ФИО и пароля.",
    },
    {
        "name": "Регионы",
        "description": "Справочник субъектов РФ (адресуются кодом субъекта) и "
        "федеральных округов.",
    },
    {
        "name": "Карта и МНО",
        "description": "Реестр мест накопления отходов с координатами для карты и "
        "заглушка синхронизации с ФГИС.",
    },
    {
        "name": "Карточка МНО",
        "description": "Детальная карточка одного места накопления отходов.",
    },
    {
        "name": "Отправка фотоотчёта",
        "description": "Публичный приём обращения из формы волонтёра (multipart, "
        "заголовок X-Intake-Token).",
    },
    {
        "name": "Добавление нового МНО",
        "description": "Ручное создание записи МНО.",
    },
    {
        "name": "Загрузка фото",
        "description": "Публичная отдача фото обращения и подсказки адреса для формы. "
        "Сама загрузка фото — внутри multipart POST /intake/form.",
    },
    {
        "name": "Админский реестр",
        "description": "Список обращений с фильтрами/сортировкой/пагинацией, воронка, "
        "карточка, смена статуса и массовые операции.",
    },
    {
        "name": "Приём вебхуков (server-to-server)",
        "description": "Внешние вебхуки приёма (Яндекс-Форма, Макс-бот) и очередь "
        "уведомлений. Не входят в мобильный API; защищены X-Intake-Token.",
    },
    {
        "name": "Экспорт (вне мобильного API)",
        "description": "Серверная выгрузка .xlsx. Не документируется для мобильного "
        "приложения.",
    },
    {
        "name": "Управление пользователями (вне мобильного API)",
        "description": "Администрирование учётных записей (только роль admin).",
    },
    {
        "name": "Интеграция ФГИС (супер-админ)",
        "description": "Синхронизация справочника регионов и мест накопления (МНО) из "
        "публичного API ФГИС УТКО (слой 5). Доступно ТОЛЬКО супер-админу. Вне "
        "мобильного API.",
    },
    {
        "name": "Служебное",
        "description": "Проверка живости сервиса.",
    },
]

app = FastAPI(
    title="ЭкоПульс API",
    version="1.0.0",
    # Swagger/OpenAPI под /api/v1/ — nginx проксирует наружу только /api/, поэтому docs/openapi
    # на корне (/docs, /openapi.json) снаружи попадали бы на SPA. Переносим под /api/v1/.
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    redoc_url="/api/v1/redoc",
    description=(
        "API административной панели эколога/инспектора «ЭкоПульс» — триаж обращений "
        "о состоянии площадок ТКО.\n\n"
        "**Base URL:** `/api/v1`\n\n"
        "**Авторизация:** для защищённых эндпоинтов — Bearer JWT "
        "(`Authorization: Bearer <access_token>` из `POST /auth/login`). "
        "Отправка фотоотчёта (`POST /intake/form`) — ПУБЛИЧНО, без токена (защита honeypot-полем "
        "`website`); `X-Intake-Token` — только на server-to-server вебхуках. Отдача фото — публично.\n\n"
        "**Конверт ошибок:** `{ \"error\": { \"code\", \"message\", \"details\" } }`.\n\n"
        "Разделы, помеченные «вне мобильного API», в клиентскую документацию не входят."
    ),
    openapi_tags=openapi_tags,
    redirect_slashes=False,
)

# CORS для фронтенда (origins из env CORS_ORIGINS, comma-separated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers — порядок важен: сначала конкретные, затем общие
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Служебное"])
async def health_check():
    return {"status": "ok"}
