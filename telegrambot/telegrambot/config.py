"""Конфигурация telegrambot (pydantic-settings, всё из .env / окружения).

Секреты — через SecretStr, никакого хардкода. Неизвестные ключи в .env
игнорируются (extra=ignore), чтобы можно было делить общий .env с backend.
"""

from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Токен Telegram-бота (из @BotFather).
    TELEGRAM_BOT_TOKEN: SecretStr

    # Эндпоинт приёма обращений на стороне backend (intake API).
    # Внутри compose-сети backend доступен по имени `backend:8000`.
    INTAKE_URL: str = "http://backend:8000/api/v1/intake/max"

    # Общий секрет X-Intake-Token (== backend YANDEX_INTAKE_TOKEN). SecretStr — чтобы не
    # светился в repr/дампах Settings (как TELEGRAM_BOT_TOKEN); наружу через get_secret_value().
    INTAKE_TOKEN: SecretStr = SecretStr("")

    # Потолок размера скачиваемого фото (защита от гигантских вложений).
    MAX_PHOTO_BYTES: int = 20 * 1024 * 1024

    # ID группового чата Telegram, откуда бот принимает фото+подпись напрямую
    # (без интерактива с МНО). Может быть отрицательным (супергруппы). None —
    # групповой сценарий не привязан к конкретному чату (бот принимает из любой
    # группы, где он участник и privacy mode выключен).
    TELEGRAM_GROUP_CHAT_ID: int | None = None

    # Период (сек) — оставлен ради паритета контракта с maxbot; групповой notify-loop
    # в Telegram-боте НЕ подключён (см. main.py: только polling).
    NOTIFY_INTERVAL: int = 15

    @field_validator("TELEGRAM_GROUP_CHAT_ID", mode="before")
    @classmethod
    def _blank_group_id_to_none(cls, v):
        """Пустая строка из env → None, а не краш каста "" → int.

        docker-compose передаёт ${TELEGRAM_GROUP_CHAT_ID:-}: если переменной нет в .env,
        в контейнер уходит ПУСТАЯ строка. Без этого валидатора pydantic уронил бы
        Settings() при импорте → весь бот падал в краш-луп (поллинг не стартовал).
        """
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def api_base(self) -> str:
        """Базовый URL backend API без хвоста intake-эндпоинта.

        Из INTAKE_URL (…/api/v1/intake/max) получаем …/api/v1 — общий префикс
        для server-to-server вызовов prepare / finalize / map.
        """
        url = self.INTAKE_URL.rstrip("/")
        suffix = "/intake/max"
        if url.endswith(suffix):
            url = url[: -len(suffix)]
        return url

    @property
    def backend_origin(self) -> str:
        """Схема + хост backend (без пути) — для сборки полных URL фото из
        относительных photo_urls вида /api/v1/intake/photo/{id}/0.jpg."""
        parts = urlsplit(self.INTAKE_URL)
        return f"{parts.scheme}://{parts.netloc}"


settings = Settings()
