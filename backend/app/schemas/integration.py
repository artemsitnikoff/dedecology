"""Схемы раздела «Интеграция ФГИС» (только супер-админ).

Формы ответов строго по контракту эндпоинтов /api/v1/integration.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RegionsOverview(BaseModel):
    """Сводка по справочнику регионов."""
    total: int
    last_sync: Optional[datetime] = None  # max(Region.last_sync)


class MnoOverview(BaseModel):
    """Сводка по МНО."""
    total: int


class PerRegionStat(BaseModel):
    """Строка сводной таблицы: сколько МНО в базе по региону + дата синхронизации."""
    code: str
    name: str
    fed: int
    mno_count: int
    last_sync: Optional[datetime] = None


class IntegrationOverview(BaseModel):
    """GET /integration/overview."""
    regions: RegionsOverview
    mno: MnoOverview
    per_region: list[PerRegionStat]


class RegionsSyncResult(BaseModel):
    """POST /integration/regions/sync — итог синхронизации справочника регионов."""
    total: int
    created: int
    updated: int
    last_sync: datetime


class MnoSyncRequest(BaseModel):
    """Тело POST /integration/mno/sync."""
    region_code: str = Field(min_length=1)


class MnoSyncStartResult(BaseModel):
    """Ответ POST /integration/mno/sync — принятая (или уже идущая) фоновая задача."""
    job_id: str
    region_code: str
    state: str  # running


class MnoSyncStatus(BaseModel):
    """GET /integration/mno/sync/status — прогресс/итог фоновой синхронизации МНО."""
    job_id: str
    region_code: str
    region_name: str
    state: str  # running | done | error
    discovered: int
    fetched: int
    upserted: int
    error: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    # Прогон по ВСЕМ регионам (scope="all"): порегионный прогресс. Для одиночной
    # задачи дефолты держат прежнюю форму (scope="region", один регион).
    scope: str = "region"          # "region" | "all"
    regions_total: int = 1
    regions_done: int = 0
    regions_failed: int = 0
    current_region: str = ""
