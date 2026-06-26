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
from .models import Incident, User

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
        session.add(
            Incident(
                source=spec["source"],
                status=spec["status"],
                fio=spec["fio"],
                region=spec["region"],
                city=spec["city"],
                street=spec["street"],
                coords=spec["coords"],
                photo_time=_parse_photo_time(spec["photoTime"]),
                photos=spec["photos"],
                photo_urls=_placeholder_urls(spec["photos"]),
                msg=spec["msg"] or None,
                bins=None,
                received_at=_parse_received(spec["dateRaw"]),
            )
        )
    logger.info("Создано инцидентов: %d", len(DEMO_INCIDENTS))


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            await seed_admin(session)
            await seed_demo_users(session)
            await seed_incidents(session)
            await session.commit()
            logger.info("Сид завершён.")
        except Exception:
            await session.rollback()
            logger.exception("Ошибка сида — откат транзакции")
            raise


if __name__ == "__main__":
    asyncio.run(main())
