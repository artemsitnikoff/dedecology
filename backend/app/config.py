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

    # Ключ Fernet для шифрования секретов, хранимых в БД (пароль SMTP и т.п.).
    # Пустой → ключ детерминированно деривируется из JWT_SECRET (см. app/core/crypto.py),
    # так что миграция/деплой работают без отдельной переменной. Задай явный
    # base64-urlsafe 32-байтный ключ (`Fernet.generate_key()`), чтобы ротация JWT_SECRET
    # НЕ обесценивала уже зашифрованные секреты.
    FERNET_KEY: str = ""
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

    # --- claude CLI (AI-разбор адреса из свободного текста Макс-обращения) ---
    # Цитаты о природе БОЛЬШЕ не через claude (берутся из БД, таблица quotes) — claude здесь
    # только для ai_parse_incident (регион/город/улица/координаты из грязного текста).
    # Долгоживущий OAuth-токен из `claude setup-token` — единственный способ авторизации CLI.
    CLAUDE_CODE_OAUTH_TOKEN: str = ""
    CLAUDE_CLI_PATH: str = "claude"
    CLAUDE_QUOTE_MODEL: str = "haiku"
    CLAUDE_QUOTE_TIMEOUT: int = 20
    # Отдельная модель для РАЗБОРА адреса из свободного текста Макс-обращения.
    # Мощнее haiku (разбор грязного текста с ФИО/датой/описанием — нетривиален);
    # цитаты остаются на CLAUDE_QUOTE_MODEL.
    CLAUDE_PARSE_MODEL: str = "sonnet"

    # Почта приложения (код подтверждения, сброс пароля) идёт через UI-SMTP (Настройки →
    # Почта, таблица smtp_settings — редактируется из админки, шифр. пароль). Отдельных
    # SMTP_* env-полей нет; остаточные SMTP_* в старых .env безвредны (model_config extra="ignore").

    # Базовый публичный URL приложения — из него собираются ссылки verify/reset
    # в письмах волонтёрам (APP_PUBLIC_URL + "/verify?token=..." и т.п.).
    APP_PUBLIC_URL: str = "https://ecopulse.reo.ru"

    # Адрес техподдержки ФГИС УТКО — получатель писем о технических ошибках
    # мобильного приложения (POST /intake/error-report). Можно переопределить env.
    SUPPORT_EMAIL: str = "ecopulse@reo.ru"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
