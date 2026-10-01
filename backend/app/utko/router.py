"""Агрегатор роутеров УТКО-совместимого API.

Все роуты несут ПОЛНЫЕ корневые пути (/connect/token, /reo-mno-events/...), поэтому
подключается в app.main БЕЗ prefix. Изолирован от /api/v1.
"""

from fastapi import APIRouter

from .auth import router as auth_router
from .routers.events import router as events_router

utko_router = APIRouter()
utko_router.include_router(auth_router)
utko_router.include_router(events_router)
