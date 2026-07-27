"""Бэкфилл УТКО-копий фото инцидентов: `{i}.jpg` → `{i}_utko.jpg`.

ФГИС УТКО отвергает фото >500 КБ, поэтому под выгрузку каждому фото инцидента нужна
отдельная «тощая» копия `{i}_utko.jpg` (≤1280×720 и ≤500000 байт). Новые фото получают
её на приёме (services/intake._store_photos, make_utko=True), а старые — этим бэкфиллом
(эндпоинт get_photo и так генерит копию лениво, но прогон разом снимает нагрузку).

Обходит {STORAGE_DIR}/incidents/*/ и для каждого FULL `{i}.jpg` (i — число), если
`{i}_utko.jpg` отсутствует (или задан --force), создаёт УТКО-копию (make_utko_copy —
тот же код, что у эндпоинта). Идемпотентно: повторный прогон без --force ничего не
пересобирает. Сбой на одном файле не роняет прогон. БД не нужна — чистый обход ФС.

Запуск из каталога backend (или в контейнере):
  docker compose -f docker-compose.prod.yml exec backend python -m app.backfill_utko_photos
      → создаёт только НЕДОСТАЮЩИЕ `{i}_utko.jpg`.
  docker compose -f docker-compose.prod.yml exec backend python -m app.backfill_utko_photos --force
      → ПЕРЕСОБИРАЕТ УТКО-копии даже если они уже есть.
"""

import logging
import re
import sys
from pathlib import Path

from .config import settings
from .services.intake import make_utko_copy

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# FULL-фото инцидента: числовой индекс + .jpg (НЕ _thumb/_utko — только исходная копия).
_FULL_RE = re.compile(r"^[0-9]+\.jpg$")


def backfill(*, force: bool) -> tuple[int, int, int]:
    """Проходит все каталоги инцидентов, создаёт недостающие УТКО-копии.

    Возвращает (created, skipped, errors). force=True — пересобирает существующие.
    """
    incidents_dir = Path(settings.STORAGE_DIR) / "incidents"
    created = 0
    skipped = 0
    errors = 0

    if not incidents_dir.is_dir():
        logger.info("[backfill_utko] каталог %s не найден — нечего делать", incidents_dir)
        return created, skipped, errors

    for inc_dir in sorted(incidents_dir.iterdir()):
        if not inc_dir.is_dir():
            continue
        for full in sorted(inc_dir.iterdir()):
            if not full.is_file() or not _FULL_RE.match(full.name):
                continue
            dest = full.with_name(f"{full.stem}_utko.jpg")
            if dest.is_file() and not force:
                skipped += 1
                continue
            try:
                make_utko_copy(full, dest)
                created += 1
            except Exception:  # noqa: BLE001 — один файл не роняет весь прогон
                errors += 1
                logger.exception(
                    "[backfill_utko] сбой УТКО-копии %s — пропускаю", full
                )

    return created, skipped, errors


def main() -> None:
    force = "--force" in sys.argv
    logger.info("[backfill_utko] старт; режим=%s", "ПЕРЕСБОРКА (--force)" if force else "недостающие")
    created, skipped, errors = backfill(force=force)
    logger.info(
        "[backfill_utko] готово: создано=%d; пропущено(уже есть)=%d; ошибок=%d",
        created,
        skipped,
        errors,
    )


if __name__ == "__main__":
    main()
