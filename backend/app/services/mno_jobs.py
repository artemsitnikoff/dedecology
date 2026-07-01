"""Хранилище прогресса фоновой синхронизации МНО в Redis.

Состояние задач ОБЩЕЕ для всех uvicorn-воркеров и arq-воркера (переживает рестарты) —
раньше реестр жил in-memory в ОДНОМ воркере, из-за чего опрос статуса попадал в другой
и отдавал 404. Теперь снимок прогресса лежит в Redis.

Ключи:
  ``mno:job:{job_id}``       — hash со снимком MnoSyncStatus (поля-строки/числа);
  ``mno:ptr:{key}``          — указатель key → job_id (key = region_code или "__all__"),
                               для дедупа запусков и опроса статуса по region_code;
  ``mno:job:{job_id}:done``  — set кодов регионов, УЖЕ пройденных в этом прогоне
                               («все регионы»), чтобы ретрай воркера возобновлялся,
                               пропуская уже сделанное;
  ``mno:cancel:{job_id}``    — флаг отмены задачи из UI (воркер прекращает краул на
                               ближайшем батче/регионе);
  ``mno:region_synced:{code}`` — постоянный маркер «регион синхронизирован» (TTL 30 сут):
                               пока жив, регион ПРОПУСКАЕТСЯ в прогоне «все регионы».

Все функции async и принимают redis-клиент (decode_responses=True) — так их удобно
покрывать офлайн FakeRedis без реального Redis.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# TTL снимка задачи / указателя / done-set / cancel-флага — сутки (потом Redis сам подчистит).
JOB_TTL = 24 * 60 * 60

# TTL постоянного маркера «регион синхронизирован» — 30 суток. Пока маркер жив, регион
# ПРОПУСКАЕТСЯ в прогоне «все регионы» (не пере-сканируем уже сделанное).
REGION_SYNCED_TTL = 30 * 24 * 60 * 60

# Задача считается «зависшей» (воркер умер/оборван деплоем/крашем), если её прогресс
# (updated_at) не обновлялся дольше этого. Тогда get_running_job её НЕ отдаёт → UI сам
# разлочивается и новый запуск проходит, без похода на сервер. Ручная «Отмена» — мгновенно.
STALE_SECONDS = 600

# Поля прогресса, приводимые к int при чтении (в Redis всё — строки).
_INT_FIELDS = (
    "discovered",
    "fetched",
    "upserted",
    "regions_total",
    "regions_done",
    "regions_failed",
)
# Поля-таймстемпы: datetime ↔ isoformat.
_DT_FIELDS = ("started_at", "finished_at", "updated_at")


def _job_key(job_id: str) -> str:
    return f"mno:job:{job_id}"


def _ptr_key(key: str) -> str:
    return f"mno:ptr:{key}"


def _done_key(job_id: str) -> str:
    return f"mno:job:{job_id}:done"


def _cancel_key(job_id: str) -> str:
    return f"mno:cancel:{job_id}"


def _region_synced_key(code: str) -> str:
    return f"mno:region_synced:{code}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def initial_progress(
    job_id: str,
    region_code: str,
    region_name: str,
    *,
    scope: str = "region",
    regions_total: int = 1,
) -> dict:
    """Начальный словарь прогресса (state=running) — форма ровно как у MnoSyncStatus."""
    return {
        "job_id": job_id,
        "region_code": region_code,
        "region_name": region_name,
        "state": "running",
        "discovered": 0,
        "fetched": 0,
        "upserted": 0,
        "error": None,
        "started_at": utcnow(),
        "finished_at": None,
        "scope": scope,
        "regions_total": regions_total,
        "regions_done": 0,
        "regions_failed": 0,
        "current_region": "",
    }


def _serialize(prog: dict) -> dict:
    """Готовит словарь к hset: None→"", datetime→isoformat, остальное→str."""
    out: dict[str, str] = {}
    for key, value in prog.items():
        if value is None:
            out[key] = ""
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = str(value)
    return out


async def write_progress(redis, job_id: str, prog: dict) -> None:
    """Пишет снимок прогресса в hash задачи (+ heartbeat updated_at) + продлевает TTL."""
    mapping = _serialize(prog)
    mapping["updated_at"] = utcnow().isoformat()  # heartbeat — для детекта зависания
    await redis.hset(_job_key(job_id), mapping=mapping)
    await redis.expire(_job_key(job_id), JOB_TTL)


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


async def read_progress(redis, job_id: str) -> dict | None:
    """Читает hash задачи и восстанавливает типы под MnoSyncStatus.

    Пустой hash (нет такой задачи) → None. Иначе dict, готовый для MnoSyncStatus(**...):
    int-поля — int(), datetime-поля — из isoformat или None, error "" → None, остальные
    (state/scope/region_*/current_region/job_id) — строки как есть.
    """
    raw = await redis.hgetall(_job_key(job_id))
    if not raw:
        return None
    prog = dict(raw)
    for field in _INT_FIELDS:
        prog[field] = _to_int(prog.get(field))
    for field in _DT_FIELDS:
        prog[field] = _to_dt(prog.get(field))
    if not prog.get("error"):
        prog["error"] = None
    return prog


async def set_pointer(redis, key: str, job_id: str) -> None:
    """Указатель key(region_code|"__all__") → текущий job_id (+ TTL)."""
    await redis.set(_ptr_key(key), job_id)
    await redis.expire(_ptr_key(key), JOB_TTL)


async def get_pointer(redis, key: str) -> str | None:
    return await redis.get(_ptr_key(key))


def is_stale(prog: dict) -> bool:
    """Задача «протухла»: heartbeat (updated_at) не двигался дольше STALE_SECONDS.

    Такое бывает, если воркер умер/оборван и hash застрял на state=running. Тогда мы
    НЕ считаем её активной — UI разлочивается сам, новый запуск проходит."""
    updated = prog.get("updated_at")
    if updated is None:
        return True  # снимок без heartbeat (старый/битый) — считаем зависшим
    return (utcnow() - updated).total_seconds() > STALE_SECONDS


async def get_running_job(redis, key: str) -> dict | None:
    """Прогресс ЖИВОЙ активной задачи по ключу (для дедупа запусков).

    По ptr берём job_id → снимок; возвращаем, только если state == "running" И задача
    НЕ протухла (is_stale). Иначе None: прежняя завершилась/упала/зависла — можно
    запускать новую (авто-разлочка без похода на сервер)."""
    job_id = await get_pointer(redis, key)
    if not job_id:
        return None
    prog = await read_progress(redis, job_id)
    if prog is not None and prog.get("state") == "running" and not is_stale(prog):
        return prog
    return None


async def mark_region_done(redis, job_id: str, region_code: str) -> None:
    """Отмечает регион пройденным в этом прогоне (для resume при ретрае воркера)."""
    await redis.sadd(_done_key(job_id), region_code)
    await redis.expire(_done_key(job_id), JOB_TTL)


async def is_region_done(redis, job_id: str, region_code: str) -> bool:
    """Пройден ли регион в этом прогоне (resume: такие пропускаем)."""
    return bool(await redis.sismember(_done_key(job_id), region_code))


# --- Отмена задачи из UI -------------------------------------------------------


async def set_cancelled(redis, job_id: str) -> None:
    """Ставит флаг отмены задачи. Воркер увидит его на ближайшем батче и прекратит краул."""
    await redis.set(_cancel_key(job_id), "1", ex=JOB_TTL)


async def is_cancelled(redis, job_id: str) -> bool:
    """Запрошена ли отмена этой задачи (проверяется воркером перед обработкой батча/региона)."""
    return bool(await redis.get(_cancel_key(job_id)))


async def clear_job(redis, key: str, job_id: str | None) -> None:
    """Снимает указатель mno:ptr:{key} → get_running_job вернёт None (UI разблокирован).

    job_id принимается для симметрии контракта (что именно снимаем), сам снимок задачи
    НЕ трогаем — он остаётся читаемым по job_id (state=cancelled), а TTL подчистит его сам."""
    await redis.delete(_ptr_key(key))


# --- Постоянный маркер «регион синхронизирован» (пропуск пройденных насовсем) ---


async def mark_region_synced(redis, code: str) -> None:
    """Метит регион успешно синхронизированным (маркер живёт REGION_SYNCED_TTL)."""
    await redis.set(_region_synced_key(code), utcnow().isoformat(), ex=REGION_SYNCED_TTL)


async def is_region_recently_synced(redis, code: str) -> bool:
    """Синхронизирован ли регион недавно (маркер ещё жив) — тогда прогон его пропускает."""
    return bool(await redis.get(_region_synced_key(code)))
