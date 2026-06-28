"""Переразбор адресов инцидентов: восстановить region/city/street/coords.

Старые инциденты (или те, где нейронка не разбила «Краснодарский край / Сочи»
и всё попало в один адрес) переразбираются через resolve_address — тот же
конвейер, что и приём из Макс-бота (AI → DaData Clean → эвристика).

Запуск из каталога backend (или в контейнере):
  docker compose -f docker-compose.prod.yml exec backend python -m app.reprocess
      → DRY-RUN: только печатает предлагаемые изменения, НИЧЕГО не пишет.
  docker compose -f docker-compose.prod.yml exec backend python -m app.reprocess --apply
      → применяет изменения + пишет audit_log, ОДИН commit в конце.
  docker compose -f docker-compose.prod.yml exec backend python -m app.reprocess --apply --all
      → то же, но по ВСЕМ инцидентам (а не только сломанным region|city пусты).

Цель по умолчанию — инциденты, где region == '' ИЛИ city == '' (явно сломанные).
Флаг --all снимает фильтр. coords переписываются ТОЛЬКО если новое непустое
(не теряем уже геокодированные). Сбой на одном инциденте не роняет весь прогон.
"""

import asyncio
import logging
import sys

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import AsyncSessionLocal
from .models import Incident
from .services.audit import audit
from .services.incident_parse import ai_parse_incident
from .services.intake import resolve_address

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Лимиты длины текстовых полей = ширине колонок БД (как в intake._FIELD_LIMITS).
_REGION_MAX = 255
_CITY_MAX = 255
_STREET_MAX = 500
_COORDS_MAX = 64


def _nz(value) -> str:
    """str | None → стрипнутая строка ('' для None)."""
    return (value or "").strip()


async def reprocess(session: AsyncSession, *, apply: bool, process_all: bool) -> None:
    """Переразбор адресов. apply=False — dry-run (без записи); commit ОДИН раз."""
    stmt = select(Incident)
    if not process_all:
        # Явно сломанные: пустой регион ИЛИ пустой город.
        stmt = stmt.where(or_(Incident.region == "", Incident.city == ""))
    stmt = stmt.order_by(Incident.created_at)
    incidents = list((await session.execute(stmt)).scalars().all())

    scanned = 0
    changed = 0
    ai_alive = 0   # сколько раз нейронка реально дала адрес (CLI жив)
    fallback = 0   # сколько ушло в DaData/эвристику (нейронка молчит/пусто)

    for inc in incidents:
        scanned += 1
        try:
            old_region, old_city, old_street, old_coords = (
                inc.region, inc.city, inc.street, inc.coords,
            )
            # Восстанавливаем текст адреса из непустых полей.
            text = ", ".join(
                p for p in (_nz(old_region), _nz(old_city), _nz(old_street)) if p
            )
            if not text:
                continue  # нечего переразбирать

            # ai парсим тут (нужно для статистики «жива ли нейронка») и отдаём
            # в resolve_address, чтобы НЕ дёргать CLI повторно.
            ai = await ai_parse_incident(text)
            if isinstance(ai, dict) and (
                _nz(ai.get("region")) or _nz(ai.get("city")) or _nz(ai.get("street"))
            ):
                ai_alive += 1
            else:
                fallback += 1

            new_region, new_city, new_street, new_coords = await resolve_address(
                text, ai=ai
            )
            new_region = new_region[:_REGION_MAX]
            new_city = new_city[:_CITY_MAX]
            new_street = new_street[:_STREET_MAX]
            new_coords = new_coords[:_COORDS_MAX]
            # coords переписываем ТОЛЬКО если новое непустое (не теряем геокод).
            final_coords = new_coords or old_coords

            if (new_region, new_city, new_street, final_coords) == (
                old_region, old_city, old_street, old_coords,
            ):
                continue  # без изменений

            changed += 1
            logger.info(
                "%s: было [%s | %s | %s | %s] → стало [%s | %s | %s | %s]",
                inc.id,
                old_region, old_city, old_street, old_coords,
                new_region, new_city, new_street, final_coords,
            )

            if apply:
                before = {
                    "region": old_region, "city": old_city,
                    "street": old_street, "coords": old_coords,
                }
                inc.region = new_region
                inc.city = new_city
                inc.street = new_street
                inc.coords = final_coords
                after = {
                    "region": new_region, "city": new_city,
                    "street": new_street, "coords": final_coords,
                }
                await audit(
                    session,
                    action="reprocess_address",
                    entity_type="incident",
                    entity_id=inc.id,
                    before=before,
                    after=after,
                    actor_user_id=None,
                    actor_type="system",
                )
        except Exception:  # noqa: BLE001 — один инцидент не роняет весь прогон
            logger.exception(
                "Ошибка переразбора инцидента %s — пропускаю",
                getattr(inc, "id", "?"),
            )
            continue

    if apply:
        await session.commit()

    mode = "ЗАПИСЬ (--apply)" if apply else "DRY-RUN (без записи)"
    target = "ВСЕ инциденты (--all)" if process_all else "сломанные (region|city пусты)"
    logger.info("[reprocess] режим=%s; цель=%s", mode, target)
    logger.info(
        "[reprocess] просмотрено=%d; %s=%d; через AI=%d; фолбэк(DaData/эвристика)=%d",
        scanned,
        "изменено" if apply else "изменится",
        changed,
        ai_alive,
        fallback,
    )


async def main() -> None:
    apply = "--apply" in sys.argv
    process_all = "--all" in sys.argv
    async with AsyncSessionLocal() as session:
        try:
            await reprocess(session, apply=apply, process_all=process_all)
            logger.info("Переразбор завершён.")
        except Exception:
            await session.rollback()
            logger.exception("Ошибка reprocess — откат транзакции")
            raise


if __name__ == "__main__":
    asyncio.run(main())
