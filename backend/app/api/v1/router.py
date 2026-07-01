"""Сборка API v1: монтирование доменных роутеров."""

from fastapi import APIRouter, Depends

from ...core.permissions import require_admin, require_superadmin
from .auth import router as auth_router
from .incidents import router as incidents_router
from .intake import router as intake_router
from .integration import router as integration_router
from .mno import router as mno_router
from .profile import router as profile_router
from .regions import fed_router as federal_districts_router
from .regions import router as regions_router
from .users import router as users_router

api_router = APIRouter()

# Теги-разделы Swagger проставлены ПОФАЙЛОВО на каждом роуте (русские названия
# разделов мобильного API), т.к. один доменный роутер может делиться на несколько
# разделов (напр. /mno → «Карта и МНО» / «Карточка МНО» / «Добавление нового МНО»).
# Поэтому здесь tags на include_router не задаются — только префиксы и зависимости.
api_router.include_router(auth_router, prefix="/auth")
api_router.include_router(incidents_router, prefix="/incidents")
api_router.include_router(mno_router, prefix="/mno")
api_router.include_router(regions_router, prefix="/regions")
api_router.include_router(federal_districts_router, prefix="/federal-districts")
# Публичный вебхук приёма Яндекс-Формы: БЕЗ auth-dependency — самозащита токеном.
api_router.include_router(intake_router, prefix="/intake")
api_router.include_router(
    users_router,
    prefix="/users",
    dependencies=[Depends(require_admin)],
)
api_router.include_router(profile_router, prefix="/profile")
# Интеграция ФГИС: раздел супер-админа (вне мобильного API) — гвард на уровне роутера.
api_router.include_router(
    integration_router,
    prefix="/integration",
    dependencies=[Depends(require_superadmin)],
)
