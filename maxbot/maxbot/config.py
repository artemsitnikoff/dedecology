"""Конфигурация maxbot (pydantic-settings, всё из .env / окружения).

Секреты — через SecretStr, никакого хардкода. Неизвестные ключи в .env
игнорируются (extra=ignore), чтобы можно было делить общий .env с backend.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Токен MAX-бота (из https://dev.max.ru).
    MAX_BOT_TOKEN: SecretStr

    # Эндпоинт приёма обращений на стороне backend (intake API).
    # Внутри compose-сети backend доступен по имени `backend:8000`.
    INTAKE_URL: str = "http://backend:8000/api/v1/intake/max"

    # Общий секрет X-Intake-Token (== backend YANDEX_INTAKE_TOKEN).
    INTAKE_TOKEN: str = ""

    # Потолок размера скачиваемого фото (защита от гигантских вложений).
    MAX_PHOTO_BYTES: int = 20 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
