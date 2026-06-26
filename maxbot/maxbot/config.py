"""Конфигурация maxbot (pydantic-settings, всё из .env / окружения).

Секреты — через SecretStr, никакого хардкода. Неизвестные ключи в .env
игнорируются (extra=ignore), чтобы можно было делить общий .env с backend.
"""

from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator
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

    # ID группового чата Макса, куда фоновый цикл постит уведомления о новых
    # обращениях (бот должен быть админом чата). Может быть отрицательным.
    # None → фоновое оповещение отключено.
    MAX_GROUP_CHAT_ID: int | None = None

    # Период опроса backend на наличие неотправленных обращений, секунды.
    NOTIFY_INTERVAL: int = 15

    @field_validator("MAX_GROUP_CHAT_ID", mode="before")
    @classmethod
    def _blank_group_id_to_none(cls, v):
        """Пустая строка из env → None (фича выключена), а не краш каста "" → int.

        docker-compose передаёт ${MAX_GROUP_CHAT_ID:-}: если переменной нет в .env,
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
        для server-to-server вызовов pending-notify / mark-notified.
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
