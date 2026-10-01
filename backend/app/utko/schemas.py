"""Pydantic-схемы ОТВЕТОВ УТКО-совместимого API.

ВАЖНО: входящие тела УТКО-эндпоинты разбирают и валидируют ВРУЧНУЮ (request.json()),
а НЕ через Pydantic-модели запроса — иначе авто-422 FastAPI перехватит глобальный конверт
{error:{...}} и тексты разойдутся с таблицами проверок доки. Поэтому здесь только схемы
ОТВЕТОВ: они дают стабильный camelCase и ISO-даты с «Z».
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer


def iso_z(dt: datetime | None) -> str | None:
    """datetime → ISO-8601 в UTC с суффиксом «Z» (как в примерах доки). None → None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class TokenResponse(BaseModel):
    """Ответ POST /connect/token (OAuth2 password grant)."""

    access_token: str
    expires_in: int
    token_type: str = "Bearer"
    refresh_token: str
    scope: str = "email offline_access openid profile"


class TruckVisitEventItem(BaseModel):
    """Элемент выдачи truck-visit-events/query (camelCase, даты с «Z»)."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: UUID
    mno_id: UUID
    event_time: datetime
    is_empty: bool
    photo_link_before: str
    photo_link_after: str
    create_date: datetime

    @field_serializer("id", "mno_id")
    def _ser_uuid(self, v: UUID) -> str:
        return str(v)

    @field_serializer("event_time", "create_date")
    def _ser_dt(self, v: datetime) -> str | None:
        return iso_z(v)

    def model_dump_camel(self) -> dict:
        return {
            "id": str(self.id),
            "mnoId": str(self.mno_id),
            "eventTime": iso_z(self.event_time),
            "isEmpty": self.is_empty,
            "photoLinkBefore": self.photo_link_before,
            "photoLinkAfter": self.photo_link_after,
            "createDate": iso_z(self.create_date),
        }


class TruckVisitQueryResponse(BaseModel):
    """Ответ truck-visit-events/query: count всего под фильтр + страница items."""

    count: int
    items: list[dict]


class VideoEventResult(BaseModel):
    """Элемент ответа video-events: пара (внешний ИД события, наш videoEventUuid)."""

    external_event_id: str | None
    video_event_uuid: UUID

    def model_dump_camel(self) -> dict:
        return {
            "externalEventId": self.external_event_id,
            "videoEventUuid": str(self.video_event_uuid),
        }
