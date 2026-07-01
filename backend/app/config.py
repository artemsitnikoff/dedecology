from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # Защита от брутфорса пароля (account lockout через БД, работает при 2+ воркерах)
    LOGIN_MAX_ATTEMPTS: int = 5      # неудачных попыток до блокировки
    LOGIN_LOCKOUT_MINUTES: int = 15  # длительность блокировки в минутах

    # Сид администратора (используется в app/seed.py — следующий этап)
    SEED_ADMIN_EMAIL: str = "admin@dedekolog.ru"
    SEED_ADMIN_PASSWORD: str = "admin12345"

    # Deployment
    CORS_ORIGINS: str = "http://localhost:5173"  # comma-separated list
    SESSION_COOKIE_SECURE: bool = False  # True в проде с HTTPS

    # Общий секрет приёма вебхуков Яндекс-Формы (заголовок X-Intake-Token).
    # None → эндпоинт приёма отключён (отдаёт INTAKE_DISABLED).
    YANDEX_INTAKE_TOKEN: str | None = None

    # DaData API-ключ — автозаполнение адреса в публичной форме волонтёра.
    # None → подсказки отключены (форма работает в режиме ручного ввода).
    DADATA_API_KEY: str | None = None

    # Секретный ключ DaData — нужен Clean API (разбор адреса из Макс-сообщений).
    # Clean API требует ОБА ключа (DADATA_API_KEY + DADATA_SECRET_KEY).
    DADATA_SECRET_KEY: str | None = None

    # Базовый URL публичного API ФГИС УТКО (интеграция «Места накопления»).
    # По умолчанию — боевой публичный хост Минприроды.
    FGIS_BASE_URL: str = "https://public-api.utko.mnr.gov.ru"

    # Redis — очередь фоновой синхронизации МНО (arq-воркер) и ОБЩИЙ прогресс задач
    # между uvicorn-воркерами: in-memory реестр жил в одном воркере, из-за чего опрос
    # статуса попадал в другой и отдавал 404. В compose host = имя сервиса `redis`.
    REDIS_URL: str = "redis://redis:6379/0"

    # Каталог хранения загруженных фото обращений (относительно cwd процесса;
    # в контейнере = /app/storage). Структура: {STORAGE_DIR}/incidents/{id}/{n}.ext
    STORAGE_DIR: str = "storage"

    # --- claude CLI (мотивирующая цитата о природе на успешном приёме) ---
    # Долгоживущий OAuth-токен из `claude setup-token`. Фолбэк, если нет CLAUDE_TOKEN_FILE.
    CLAUDE_CODE_OAUTH_TOKEN: str = ""
    # Путь к общему токен-файлу claude (JSON {access_token, ...}); читаем на каждый вызов,
    # имеет приоритет над CLAUDE_CODE_OAUTH_TOKEN. Монтируется в контейнер.
    CLAUDE_TOKEN_FILE: str = ""
    CLAUDE_CLI_PATH: str = "claude"
    CLAUDE_QUOTE_MODEL: str = "haiku"
    CLAUDE_QUOTE_TIMEOUT: int = 20
    # Отдельная модель для РАЗБОРА адреса из свободного текста Макс-обращения.
    # Мощнее haiku (разбор грязного текста с ФИО/датой/описанием — нетривиален);
    # цитаты остаются на CLAUDE_QUOTE_MODEL.
    CLAUDE_PARSE_MODEL: str = "sonnet"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
