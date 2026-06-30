"""Сборка API v1: монтирование доменных роутеров."""

from fastapi import APIRouter, Depends

from ...core.permissions import require_admin
from .auth import router as auth_router
from .incidents import router as incidents_router
from .intake import router as intake_router
from .mno import router as mno_router
from .profile import router as profile_router
from .regions import fed_router as federal_districts_router
from .regions import router as regions_router
from .users import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(incidents_router, prefix="/incidents", tags=["incidents"])
api_router.include_router(mno_router, prefix="/mno", tags=["mno"])
api_router.include_router(regions_router, prefix="/regions", tags=["regions"])
api_router.include_router(
    federal_districts_router, prefix="/federal-districts", tags=["federal-districts"]
)
# Публичный вебхук приёма Яндекс-Формы: БЕЗ auth-dependency — самозащита токеном.
api_router.include_router(intake_router, prefix="/intake", tags=["intake"])
api_router.include_router(
    users_router,
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_admin)],
)
api_router.include_router(profile_router, prefix="/profile", tags=["profile"])
