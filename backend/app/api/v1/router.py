"""Сборка API v1: монтирование доменных роутеров."""

from fastapi import APIRouter, Depends

from ...core.permissions import require_admin, require_superadmin
from .auth import router as auth_router
from .blocked_domains import router as blocked_domains_router
from .incident_types import router as incident_types_router
from .incidents import router as incidents_router
from .intake import router as intake_router
from .integration import router as integration_router
from .mno import router as mno_router
from .profile import router as profile_router
from .regions import fed_router as federal_districts_router
from .regions import router as regions_router
from .reports import router as reports_router
from .smtp import router as smtp_router
from .users import router as users_router
from .volunteer import router as volunteer_router
from .volunteers import router as volunteers_router

api_router = APIRouter()

# Теги-разделы Swagger проставлены ПОФАЙЛОВО на каждом роуте (русские названия
# разделов мобильного API), т.к. один доменный роутер может делиться на несколько
# разделов (напр. /mno → «Карта и МНО» / «Карточка МНО» / «Добавление нового МНО»).
# Поэтому здесь tags на include_router не задаются — только префиксы и зависимости.
api_router.include_router(auth_router, prefix="/auth")
api_router.include_router(incidents_router, prefix="/incidents")
# Отчёты — история Excel-выгрузок обращений; доступ любому авторизованному, БЕЗ admin-гейта.
api_router.include_router(reports_router, prefix="/reports")
api_router.include_router(mno_router, prefix="/mno")
api_router.include_router(regions_router, prefix="/regions")
api_router.include_router(federal_districts_router, prefix="/federal-districts")
# Справочник «Типы инцидентов»: GET — авторизованным (гвард get_current_user на
# роуте), мутации — под require_admin (Depends на каждом мутирующем эндпоинте).
api_router.include_router(incident_types_router, prefix="/incident-types")
# Справочник «Стоп-лист почтовых доменов»: все роуты (GET/POST/DELETE) — только admin
# (Depends(require_admin) на каждом эндпоинте). Блокирует регистрацию волонтёра по домену.
api_router.include_router(blocked_domains_router, prefix="/blocked-domains")
# Публичный вебхук приёма Яндекс-Формы: БЕЗ auth-dependency — самозащита токеном.
api_router.include_router(intake_router, prefix="/intake")
api_router.include_router(
    users_router,
    prefix="/users",
    dependencies=[Depends(require_admin)],
)
api_router.include_router(profile_router, prefix="/profile")
# Настройки SMTP: раздел «Настройки», только admin — гвард на уровне роутера.
api_router.include_router(
    smtp_router,
    prefix="/settings/smtp",
    dependencies=[Depends(require_admin)],
)
# Интеграция ФГИС: раздел супер-админа (вне мобильного API) — гвард на уровне роутера.
api_router.include_router(
    integration_router,
    prefix="/integration",
    dependencies=[Depends(require_superadmin)],
)
# Волонтёры (мобильное приложение): контур самообслуживания — БЕЗ admin-гейта
# (регистрация/логин/сброс публичны; /me и /onboarding защищены get_current_volunteer).
api_router.include_router(volunteer_router, prefix="/volunteer")
# Админ-справочник «Волонтёры»: просмотр + блокировка/удаление, только admin.
api_router.include_router(
    volunteers_router,
    prefix="/volunteers",
    dependencies=[Depends(require_admin)],
)
