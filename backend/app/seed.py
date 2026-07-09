"""Идемпотентный сид: админ + 2 демо-юзера + 13 демо-инцидентов.

Запуск из каталога backend:  python -m app.seed
Все вставки с exists-guard — повторный запуск не плодит дубликаты.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .core.security import get_password_hash
from .database import AsyncSessionLocal
from .models import Incident, Mno, Region, User
from .services.geo import parse_latlon
from .services.quotes import seed_quotes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# --- Демо-пользователи (кроме админа из settings) ---
DEMO_USERS = [
    {
        "email": "operator@dedekolog.ru",
        "password": "operator12345",
        "fio": "Иванова Светлана Петровна",
        "role": "user",
        "status": "active",
    },
    {
        "email": "invited@dedekolog.ru",
        "password": "invited12345",
        "fio": "Кузьмин Олег Андреевич",
        "role": "user",
        "status": "invited",
    },
]


# --- 13 демо-инцидентов из project/react-app/data.js ---
DEMO_INCIDENTS = [
    {"source": "max", "status": "found", "fio": "Громов Сергей Петрович", "region": "Самарская область", "city": "пгт Усть-Кинельский", "street": "Бульварная улица, 18 (Радар №116320)", "coords": "53.231410, 50.166820", "photoTime": "25.04.2026, 09:14", "photos": 2, "msg": "max-msg-116320", "dateRaw": "2026-04-26 08:42"},
    {"source": "form", "status": "new", "fio": "Андреева Мария Игоревна", "region": "Новгородская область", "city": "Великий Новгород", "street": "ул. Радужная, 15", "coords": "55.859624, 37.663597", "photoTime": "26.04.2026, 11:30", "photos": 3, "msg": "", "dateRaw": "2026-04-26 11:48"},
    {"source": "max", "status": "new", "fio": "Сидоров Иван Алексеевич", "region": "Самарская область", "city": "г. Кинель", "street": "ул. Маяковского, 41 (Радар №118044)", "coords": "53.222900, 50.629100", "photoTime": "26.04.2026, 08:05", "photos": 1, "msg": "max-msg-118044", "dateRaw": "2026-04-26 08:11"},
    {"source": "form", "status": "found", "fio": "Кузнецова Ольга Дмитриевна", "region": "Москва", "city": "Зеленоград", "street": "корпус 1462", "coords": "55.991400, 37.214700", "photoTime": "25.04.2026, 17:22", "photos": 3, "msg": "", "dateRaw": "2026-04-25 17:40"},
    {"source": "max", "status": "none", "fio": "Морозов Дмитрий Олегович", "region": "Самарская область", "city": "с. Сырейка", "street": "ул. Центральная, 7 (Радар №115980)", "coords": "53.301200, 50.420000", "photoTime": "24.04.2026, 14:48", "photos": 2, "msg": "max-msg-115980", "dateRaw": "2026-04-24 15:02"},
    {"source": "form", "status": "exported", "fio": "Петров Алексей Юрьевич", "region": "Санкт-Петербург", "city": "Санкт-Петербург", "street": "пр. Космонавтов, 28", "coords": "59.852300, 30.350100", "photoTime": "22.04.2026, 10:05", "photos": 2, "msg": "", "dateRaw": "2026-04-22 10:20"},
    {"source": "max", "status": "found", "fio": "Васильева Наталья Сергеевна", "region": "Самарская область", "city": "пгт Усть-Кинельский", "street": "Спортивная улица, 4 (Радар №116401)", "coords": "53.232000, 50.170300", "photoTime": "26.04.2026, 07:51", "photos": 3, "msg": "max-msg-116401", "dateRaw": "2026-04-26 07:55"},
    {"source": "form", "status": "new", "fio": "Орлов Михаил Викторович", "region": "Республика Татарстан", "city": "Казань", "street": "ул. Чистопольская, 61А", "coords": "55.821700, 49.111300", "photoTime": "26.04.2026, 12:40", "photos": 1, "msg": "", "dateRaw": "2026-04-26 12:51"},
    {"source": "max", "status": "exported", "fio": "Зайцева Екатерина Павловна", "region": "Самарская область", "city": "г. Кинель", "street": "ул. 27 Партсъезда, 1Б (Радар №117210)", "coords": "53.220100, 50.638400", "photoTime": "21.04.2026, 16:18", "photos": 2, "msg": "max-msg-117210", "dateRaw": "2026-04-21 16:30"},
    {"source": "form", "status": "none", "fio": "Лебедев Артём Романович", "region": "Нижегородская область", "city": "Нижний Новгород", "street": "ул. Бекетова, 13", "coords": "56.288800, 43.991200", "photoTime": "23.04.2026, 09:36", "photos": 2, "msg": "", "dateRaw": "2026-04-23 09:50"},
    {"source": "max", "status": "found", "fio": "Соколова Анна Витальевна", "region": "Самарская область", "city": "пос. Алексеевка", "street": "ул. Невская, 22 (Радар №116770)", "coords": "53.181000, 50.020500", "photoTime": "26.04.2026, 06:42", "photos": 3, "msg": "max-msg-116770", "dateRaw": "2026-04-26 06:48"},
    {"source": "form", "status": "new", "fio": "Никитин Павел Андреевич", "region": "Свердловская область", "city": "Екатеринбург", "street": "ул. Сулимова, 38", "coords": "56.851200, 60.617900", "photoTime": "25.04.2026, 19:10", "photos": 2, "msg": "", "dateRaw": "2026-04-25 19:22"},
    {"source": "max", "status": "exported", "fio": "Фёдорова Юлия Олеговна", "region": "Самарская область", "city": "г. Кинель", "street": "ул. Фестивальная, 9 (Радар №117905)", "coords": "53.225600, 50.641000", "photoTime": "20.04.2026, 13:27", "photos": 1, "msg": "max-msg-117905", "dateRaw": "2026-04-20 13:35"},
]


# --- 8 регионов справочника (совпадают с регионами демо-инцидентов; нумерация ФГИС) ---
DEMO_REGIONS = [
    {"code": "63", "name": "Самарская область", "fed": 5, "operators": ["ЭкоСтройРесурс"], "active": True, "lastSync": "2026-04-26 06:30"},
    {"code": "77", "name": "Москва", "fed": 1, "operators": ["ГБУ «Экотехпром»", "МКМ-Логистика", "Хартия", "МСК-НТ"], "active": True, "lastSync": "2026-04-25 07:00"},
    {"code": "78", "name": "Санкт-Петербург", "fed": 2, "operators": ["Невский экологический оператор"], "active": True, "lastSync": "2026-04-22 09:00"},
    {"code": "16", "name": "Республика Татарстан", "fed": 5, "operators": ["УК «ПЖКХ»", "Гринта"], "active": True, "lastSync": "2026-04-24 08:00"},
    {"code": "52", "name": "Нижегородская область", "fed": 5, "operators": ["«Нижэкология-НН»", "Реал-Кстово", "МСК-НТ"], "active": True, "lastSync": "2026-04-23 08:00"},
    {"code": "66", "name": "Свердловская область", "fed": 6, "operators": ["«Спецавтобаза»", "Рифей", "ТБО «Экосервис»"], "active": True, "lastSync": "2026-04-25 10:00"},
    {"code": "53", "name": "Новгородская область", "fed": 2, "operators": ["«Спецавтохозяйство»"], "active": True, "lastSync": "2026-04-20 06:00"},
    {"code": "73", "name": "Ульяновская область", "fed": 5, "operators": [], "active": False, "lastSync": ""},
]


# --- 15 МНО в этих регионах: ~10 synced (с fgis_id+sync_date), ~5 вручную (synced=False) ---
DEMO_MNO = [
    {"reg": "63-04-001162", "name": "Контейнерная площадка, ул. Бульварная, 18", "region_code": "63", "city": "пгт Усть-Кинельский", "address": "Бульварная улица, 18", "coords": "53.231410, 50.166820", "synced": True, "syncDate": "2026-04-26 06:30", "fgisId": "02e29deb-1aa8-4949-a1c2-8db71252acb6", "incidents": 1},
    {"reg": "63-04-001180", "name": "Контейнерная площадка, ул. Маяковского, 41", "region_code": "63", "city": "г. Кинель", "address": "ул. Маяковского, 41", "coords": "53.222900, 50.629100", "synced": True, "syncDate": "2026-04-26 06:30", "fgisId": "1b6f3c20-7d11-4a8e-9f02-2c44a1e6b730", "incidents": 1},
    {"reg": "63-04-000159", "name": "Контейнерная площадка, ул. Центральная, 7", "region_code": "63", "city": "с. Сырейка", "address": "ул. Центральная, 7", "coords": "53.301200, 50.420000", "synced": True, "syncDate": "2026-04-26 06:30", "fgisId": "9c7a44e1-0b53-4f6d-8a21-6e9d0c12fa84", "incidents": 1},
    {"reg": "63-04-001164", "name": "Контейнерная площадка, ул. Спортивная, 4", "region_code": "63", "city": "пгт Усть-Кинельский", "address": "Спортивная улица, 4", "coords": "53.232000, 50.170300", "synced": False, "syncDate": None, "fgisId": "4d2e8810-5a6b-4c3d-b1f7-7a0e9d551c22", "incidents": 1},
    {"reg": "63-04-001172", "name": "Контейнерная площадка, ул. 27 Партсъезда, 1Б", "region_code": "63", "city": "г. Кинель", "address": "ул. 27 Партсъезда, 1Б", "coords": "53.220100, 50.638400", "synced": True, "syncDate": "2026-04-26 06:30", "fgisId": "7f10a3b9-2c84-49e1-a6d3-0b5f8e44d910", "incidents": 1},
    {"reg": "63-04-001167", "name": "Контейнерная площадка, ул. Невская, 22", "region_code": "63", "city": "пос. Алексеевка", "address": "ул. Невская, 22", "coords": "53.181000, 50.020500", "synced": True, "syncDate": "2026-04-26 06:30", "fgisId": "a3c91f57-6d20-4b8a-9e14-3f7c2d60ab85", "incidents": 1},
    {"reg": "63-04-001179", "name": "Контейнерная площадка, ул. Фестивальная, 9", "region_code": "63", "city": "г. Кинель", "address": "ул. Фестивальная, 9", "coords": "53.225600, 50.641000", "synced": True, "syncDate": "2026-04-26 06:30", "fgisId": "c5e07b42-8a19-4d63-b2f0-1e9a4c87d536", "incidents": 1},
    {"reg": "63-04-001181", "name": "Контейнерная площадка, ул. Украинская, 3", "region_code": "63", "city": "г. Кинель", "address": "ул. Украинская, 3", "coords": "53.228000, 50.632000", "synced": True, "syncDate": "2026-04-26 06:30", "fgisId": "e81d2a64-3f57-4c90-a7b1-5d0e6b29f413", "incidents": 0},
    {"reg": "63-04-001165", "name": "Контейнерная площадка, ул. Шоссейная, 12", "region_code": "63", "city": "пгт Усть-Кинельский", "address": "Шоссейная улица, 12", "coords": "53.236000, 50.158000", "synced": True, "syncDate": "2026-04-26 06:30", "fgisId": "6b4f9c07-1e83-42da-90c5-8a2d7f015e6b", "incidents": 0},
    {"reg": "77-18-004521", "name": "Контейнерная площадка, корпус 1462", "region_code": "77", "city": "Зеленоград", "address": "корпус 1462", "coords": "55.991400, 37.214700", "synced": True, "syncDate": "2026-04-25 07:00", "fgisId": "d7a3e510-9b26-4f81-8c04-2e6b1a93c7d8", "incidents": 1},
    {"reg": "78-06-002210", "name": "Контейнерная площадка, пр. Космонавтов, 28", "region_code": "78", "city": "Санкт-Петербург", "address": "пр. Космонавтов, 28", "coords": "59.852300, 30.350100", "synced": True, "syncDate": "2026-04-22 09:00", "fgisId": "0f5c8b21-7a40-4e63-9d12-4b8e0a6f3c95", "incidents": 1},
    {"reg": "16-01-003344", "name": "Контейнерная площадка, ул. Чистопольская, 61А", "region_code": "16", "city": "Казань", "address": "ул. Чистопольская, 61А", "coords": "55.821700, 49.111300", "synced": False, "syncDate": None, "fgisId": "b29d4e76-5c81-403a-8f25-7a1c6d09e482", "incidents": 1},
    {"reg": "52-01-002901", "name": "Контейнерная площадка, ул. Бекетова, 13", "region_code": "52", "city": "Нижний Новгород", "address": "ул. Бекетова, 13", "coords": "56.288800, 43.991200", "synced": True, "syncDate": "2026-04-23 08:00", "fgisId": "38e1c9a0-6b47-4d52-91f8-0c5a2e74b613", "incidents": 1},
    {"reg": "66-01-005012", "name": "Контейнерная площадка, ул. Сулимова, 38", "region_code": "66", "city": "Екатеринбург", "address": "ул. Сулимова, 38", "coords": "56.851200, 60.617900", "synced": True, "syncDate": "2026-04-25 10:00", "fgisId": "5a0b7f33-2d68-4c19-a8e4-9f1d6037b285", "incidents": 1},
    {"reg": "53-01-000412", "name": "Контейнерная площадка, ул. Радужная, 15", "region_code": "53", "city": "Великий Новгород", "address": "ул. Радужная, 15", "coords": "58.521800, 31.275000", "synced": False, "syncDate": None, "fgisId": "91c46de8-0a72-4b35-86f1-3d8e2a5c049b", "incidents": 1},
]


def _parse_photo_time(value: str) -> datetime:
    """'DD.MM.YYYY, HH:MM' → datetime (tz-aware UTC)."""
    return datetime.strptime(value, "%d.%m.%Y, %H:%M").replace(tzinfo=timezone.utc)


def _parse_received(value: str) -> datetime:
    """'YYYY-MM-DD HH:MM' → datetime (tz-aware UTC)."""
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def _placeholder_urls(n: int) -> list[str]:
    """N плейсхолдер-строк для photo_urls (реальных файлов пока нет — честно подписываем)."""
    return [f"placeholder://incident-photo/{i + 1}" for i in range(max(1, n))]


async def seed_admin(session: AsyncSession) -> None:
    email = settings.SEED_ADMIN_EMAIL
    existing = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing is not None:
        logger.info("Админ уже существует: %s", email)
        return
    session.add(
        User(
            email=email,
            password_hash=get_password_hash(settings.SEED_ADMIN_PASSWORD),
            fio="Дед Эколог",
            role="admin",
            status="active",
            is_active=True,
            is_superadmin=True,
        )
    )
    logger.info("Создан админ: %s", email)


async def seed_demo_users(session: AsyncSession) -> None:
    for spec in DEMO_USERS:
        existing = (
            await session.execute(select(User).where(User.email == spec["email"]))
        ).scalar_one_or_none()
        if existing is not None:
            logger.info("Пользователь уже существует: %s", spec["email"])
            continue
        session.add(
            User(
                email=spec["email"],
                password_hash=get_password_hash(spec["password"]),
                fio=spec["fio"],
                role=spec["role"],
                status=spec["status"],
                is_active=True,
            )
        )
        logger.info("Создан пользователь: %s (%s/%s)", spec["email"], spec["role"], spec["status"])


async def seed_incidents(session: AsyncSession) -> None:
    existing_count = (
        await session.execute(select(func.count(Incident.id)))
    ).scalar_one()
    if existing_count > 0:
        logger.info("Инциденты уже засеяны (%d шт.) — пропускаю", existing_count)
        return
    for spec in DEMO_INCIDENTS:
        lat, lon = parse_latlon(spec["coords"])
        session.add(
            Incident(
                source=spec["source"],
                status=spec["status"],
                fio=spec["fio"],
                region=spec["region"],
                city=spec["city"],
                street=spec["street"],
                coords=spec["coords"],
                lat=lat,
                lon=lon,
                photo_time=_parse_photo_time(spec["photoTime"]),
                photos=spec["photos"],
                photo_urls=_placeholder_urls(spec["photos"]),
                msg=spec["msg"] or None,
                bins=None,
                received_at=_parse_received(spec["dateRaw"]),
            )
        )
    logger.info("Создано инцидентов: %d", len(DEMO_INCIDENTS))


async def seed_regions(session: AsyncSession) -> None:
    """8 регионов справочника (exists-guard по числу строк — идемпотентно)."""
    existing_count = (
        await session.execute(select(func.count(Region.id)))
    ).scalar_one()
    if existing_count > 0:
        logger.info("Регионы уже засеяны (%d шт.) — пропускаю", existing_count)
        return
    for spec in DEMO_REGIONS:
        session.add(
            Region(
                code=spec["code"],
                name=spec["name"],
                fed=spec["fed"],
                operators=spec["operators"],
                active=spec["active"],
                last_sync=_parse_received(spec["lastSync"]) if spec["lastSync"] else None,
            )
        )
    logger.info("Создано регионов: %d", len(DEMO_REGIONS))


async def seed_mno(session: AsyncSession) -> None:
    """15 МНО в засеянных регионах (exists-guard по числу строк — идемпотентно)."""
    existing_count = (
        await session.execute(select(func.count(Mno.id)))
    ).scalar_one()
    if existing_count > 0:
        logger.info("МНО уже засеяны (%d шт.) — пропускаю", existing_count)
        return
    for spec in DEMO_MNO:
        lat, lon = parse_latlon(spec["coords"])
        session.add(
            Mno(
                reg=spec["reg"],
                name=spec["name"],
                region_code=spec["region_code"],
                city=spec["city"],
                address=spec["address"],
                coords=spec["coords"],
                lat=lat,
                lon=lon,
                fgis_id=spec["fgisId"],
                synced=spec["synced"],
                sync_date=_parse_received(spec["syncDate"]) if spec["syncDate"] else None,
                incidents=spec["incidents"],
            )
        )
    synced_n = sum(1 for s in DEMO_MNO if s["synced"])
    logger.info("Создано МНО: %d (synced=%d, вручную=%d)", len(DEMO_MNO), synced_n, len(DEMO_MNO) - synced_n)


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            await seed_admin(session)
            await seed_demo_users(session)
            await seed_incidents(session)
            await seed_regions(session)
            await seed_mno(session)
            await seed_quotes(session)
            await session.commit()
            logger.info("Сид завершён.")
        except Exception:
            await session.rollback()
            logger.exception("Ошибка сида — откат транзакции")
            raise


if __name__ == "__main__":
    asyncio.run(main())
