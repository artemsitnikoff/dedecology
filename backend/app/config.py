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

    # Каталог хранения загруженных фото обращений (относительно cwd процесса;
    # в контейнере = /app/storage). Структура: {STORAGE_DIR}/incidents/{id}/{n}.ext
    STORAGE_DIR: str = "storage"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
