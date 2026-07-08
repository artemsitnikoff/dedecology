"""Схемы SMTP-настроек (request-модели).

Статус (GET) отдаётся сервисом как обычный dict (пароль в нём отсутствует по
построению — отдельная response-модель не нужна, чтобы случайно не «протащить»
секрет). Валидация значений (порт/режим/почта) — в сервисе (единый источник
ошибок для теста и сохранения).
"""

from pydantic import BaseModel


class SmtpConfigRequest(BaseModel):
    host: str
    port: int
    encryption: str = "ssl"
    username: str = ""
    # Пароль write-only: пусто при уже сохранённой конфигурации → старый пароль
    # сохраняется; наружу (в GET-статусе) не возвращается никогда.
    password: str = ""
    from_email: str
    from_name: str = ""


class SmtpTestRequest(BaseModel):
    to: str
