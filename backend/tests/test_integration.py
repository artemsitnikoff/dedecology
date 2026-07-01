"""Тесты раздела «Интеграция ФГИС» — офлайн (httpx/сессия/Redis мокаются).

Покрытие:
  - JSONP-парсер (снятие обёртки, пустой/битый ответ);
  - split_bbox_2x2;
  - краулер enumerate_region_mno_ids (дробление большого кластера + сбор без дублей,
    фолбэк на MAX_Z);
  - REGION_FED (значения 1..8, типовые коды);
  - sync_regions (id→code, сохранение operators/active при update);
  - require_superadmin (ForbiddenError для не-суперадмина);
  - хранилище прогресса в Redis (mno_jobs) на FakeRedis: round-trip типов, указатели,
    дедуп, done-set для resume;
  - воркер (mno_worker) на FakeRedis + мок fgis/сессии: один регион, все регионы,
    resume (skip done), per-region ошибка;
  - эндпоинты /integration (мок сервиса/Redis/arq-пула): overview, regions/sync,
    mno/sync (+404/503/дедуп), mno/sync-all (+400/503/дедуп), status (+404).
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.core.errors import AppError, ForbiddenError
from app.core.permissions import require_superadmin
from app.main import app
from app.models import Region, User
from app.schemas.integration import (
    IntegrationOverview,
    MnoOverview,
    MnoSyncStatus,
    RegionsOverview,
    RegionsSyncResult,
)
from app.services import fgis, mno_jobs, mno_sync, mno_worker
from app.services.fgis import parse_jsonp, split_bbox_2x2
from app.services.region_fed import REGION_FED, region_fed


# --- FakeRedis: минимальный async-Redis на dict (офлайн, без сети) -------------


class FakeRedis:
    """Поддельный redis.asyncio-клиент (decode_responses=True) на обычных dict.

    Хранит строки — как реальный Redis с decode_responses=True; mno_jobs сам
    восстанавливает типы при чтении."""

    def __init__(self):
        self.hashes: dict[str, dict[str, str]] = {}
        self.strings: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}

    async def hset(self, name, mapping=None, **kwargs):
        h = self.hashes.setdefault(name, {})
        if mapping:
            h.update(mapping)
        h.update(kwargs)
        return len(h)

    async def hgetall(self, name):
        return dict(self.hashes.get(name, {}))

    async def expire(self, name, ttl):
        return True

    async def set(self, name, value, ex=None):
        # ex (TTL) принимаем для совместимости с реальным клиентом; офлайн его не эмулируем.
        self.strings[name] = value
        return True

    async def get(self, name):
        return self.strings.get(name)

    async def sadd(self, name, *values):
        s = self.sets.setdefault(name, set())
        before = len(s)
        s.update(values)
        return len(s) - before

    async def sismember(self, name, value):
        return 1 if value in self.sets.get(name, set()) else 0

    async def smembers(self, name):
        return set(self.sets.get(name, set()))

    async def delete(self, *names):
        removed = 0
        for name in names:
            for store in (self.hashes, self.strings, self.sets):
                if name in store:
                    del store[name]
                    removed += 1
        return removed


@pytest.fixture(autouse=True)
def _reset_arq_pool():
    """Каждый тест стартует без arq-пула (lifespan в ASGI-тестах не поднимается).

    Тесты, которым нужен пул, ставят app.state.arq_pool сами; здесь только чистим,
    чтобы состояние не протекало между тестами."""
    app.state.arq_pool = None
    yield
    app.state.arq_pool = None


# --- JSONP-парсер --------------------------------------------------------------


def test_parse_jsonp_unwraps_callback():
    text = 'callback({"type":"FeatureCollection","features":[{"properties":{"id":"abc"}}]});'
    data = parse_jsonp(text)
    assert data["type"] == "FeatureCollection"
    assert data["features"][0]["properties"]["id"] == "abc"


def test_parse_jsonp_unwraps_without_semicolon():
    text = 'callback({"features":[]})'
    assert parse_jsonp(text)["features"] == []


def test_parse_jsonp_empty_features():
    text = 'callback({"type":"FeatureCollection","features":[]});'
    assert parse_jsonp(text)["features"] == []


def test_parse_jsonp_blank_returns_empty_collection():
    assert parse_jsonp("")["features"] == []
    assert parse_jsonp("   ")["features"] == []


def test_parse_jsonp_garbage_degrades():
    # Битый JSON внутри обёртки → пустая коллекция, без исключения.
    assert parse_jsonp("callback(not-json);")["features"] == []


def test_split_bbox_2x2():
    subs = split_bbox_2x2((0, 0, 10, 20))
    assert len(subs) == 4
    assert (0, 0, 5, 10) in subs
    assert (5, 10, 10, 20) in subs


# --- Краулер enumerate_region_mno_ids ------------------------------------------


@pytest.mark.asyncio
async def test_crawler_splits_big_cluster_and_dedups(monkeypatch):
    """Большой кластер (iconContent>100) дробится 2×2; малые кластеры и одиночки
    собираются без дублей; обрезанные id большого кластера НЕ попадают в выборку."""
    # Один стартовый цель-квадрат, чтобы обход был детерминированным.
    monkeypatch.setattr(fgis, "START_CELLS", [(0, 0, 10, 10)])
    monkeypatch.setattr(fgis, "START_Z", 4)

    calls: list = []

    async def fake_fetch_tile(filter_id, bbox, z):
        calls.append((bbox, z))
        n = len(calls)
        if n == 1:
            # Большой кластер: total=250 > 100, z=4 < MAX_Z → должен раздробиться,
            # обрезанные "x*" в выборку НЕ идут.
            return [
                {
                    "properties": {
                        "layer": 5,
                        "ids": [f"x{i}" for i in range(100)],
                        "iconContent": "250",
                    }
                }
            ]
        # 4 подъячейки: одиночка + общий id (дедуп) + малый кластер + общий cluster-id.
        return [
            {"properties": {"layer": 5, "id": f"single-{n}"}},
            {"properties": {"layer": 5, "id": "SHARED"}},
            {"properties": {"layer": 5, "ids": [f"c{n}", "SHARED-CL"], "iconContent": "2"}},
        ]

    monkeypatch.setattr(fgis, "fetch_tile", fake_fetch_tile)

    ids, issues = await fgis.enumerate_region_mno_ids("filter-uuid", 51)

    # 1 стартовая ячейка + 4 подъячейки = 5 tile-запросов.
    assert len(calls) == 5
    # Подъячейки ушли на зум START_Z+2 = 6.
    assert all(z == 6 for _bbox, z in calls[1:])
    # Обрезанные id большого кластера НЕ добавлены (кластер раздроблён, не взят).
    assert "x0" not in ids
    # Собрано: single-2..single-5 (4) + SHARED (1) + c2..c5 (4) + SHARED-CL (1) = 10.
    assert ids == {
        "single-2", "single-3", "single-4", "single-5",
        "SHARED", "c2", "c3", "c4", "c5", "SHARED-CL",
    }
    assert len(ids) == 10  # дубли SHARED/SHARED-CL схлопнуты
    assert issues == []


@pytest.mark.asyncio
async def test_crawler_maxz_fallback_takes_truncated(monkeypatch):
    """На MAX_Z большой кластер не дробится — берём обрезанные id + запись в issues."""
    monkeypatch.setattr(fgis, "START_CELLS", [(0, 0, 10, 10)])
    monkeypatch.setattr(fgis, "START_Z", fgis.MAX_Z)  # стартуем уже на макс. зуме

    async def fake_fetch_tile(filter_id, bbox, z):
        return [
            {"properties": {"layer": 5, "ids": ["a", "b", "c"], "iconContent": "500"}}
        ]

    monkeypatch.setattr(fgis, "fetch_tile", fake_fetch_tile)

    ids, issues = await fgis.enumerate_region_mno_ids("f", 51)
    assert ids == {"a", "b", "c"}
    assert len(issues) == 1
    assert "макс" in issues[0].lower()


@pytest.mark.asyncio
async def test_crawler_progress_callback(monkeypatch):
    monkeypatch.setattr(fgis, "START_CELLS", [(0, 0, 10, 10)])
    monkeypatch.setattr(fgis, "START_Z", 4)

    async def fake_fetch_tile(filter_id, bbox, z):
        return [{"properties": {"layer": 5, "id": "one"}}]

    monkeypatch.setattr(fgis, "fetch_tile", fake_fetch_tile)

    seen: list = []
    ids, _ = await fgis.enumerate_region_mno_ids(
        "f", 51, on_progress=lambda n: seen.append(n)
    )
    assert ids == {"one"}
    assert seen and seen[-1] == 1


@pytest.mark.asyncio
async def test_crawler_on_batch_streams_new_ids(monkeypatch):
    """С on_batch краулер отдаёт НОВЫЕ id батчами (≤ batch_size) ПОТОКОВО, не дожидаясь
    конца обхода: сумма всех батчей == seen, размеры ≤100, остаток слит последним
    (неполным) вызовом, дублей нет."""
    monkeypatch.setattr(fgis, "START_CELLS", [(0, 0, 10, 10)])
    monkeypatch.setattr(fgis, "START_Z", 4)

    async def fake_fetch_tile(filter_id, bbox, z):
        # 100 + 100 + 1 = 201 уникальных id в одной ячейке (кластеры ≤100 берутся целиком).
        return [
            {"properties": {"layer": 5, "ids": [f"c{i}" for i in range(100)], "iconContent": "100"}},
            {"properties": {"layer": 5, "ids": [f"d{i}" for i in range(100)], "iconContent": "100"}},
            {"properties": {"layer": 5, "id": "s1"}},
        ]

    monkeypatch.setattr(fgis, "fetch_tile", fake_fetch_tile)

    batches: list[list[str]] = []

    async def on_batch(ids: list[str]) -> None:
        batches.append(list(ids))

    seen, issues = await fgis.enumerate_region_mno_ids(
        "f", 51, on_batch=on_batch, batch_size=100
    )

    assert issues == []
    assert len(seen) == 201
    # Полные батчи по 100 + слитый остаток: [100, 100, 1].
    assert [len(b) for b in batches] == [100, 100, 1]
    assert all(len(b) <= 100 for b in batches)
    # Остаток слит ПОСЛЕДНИМ вызовом (последний батч неполный).
    assert len(batches[-1]) == 1
    # Сумма всех батчей == seen, без дублей.
    flat = [x for b in batches for x in b]
    assert len(flat) == len(set(flat)) == len(seen)
    assert set(flat) == seen


@pytest.mark.asyncio
async def test_crawler_without_on_batch_collects_full_set(monkeypatch):
    """Обратная совместимость: без on_batch краулер собирает полный set и ничего не флашит."""
    monkeypatch.setattr(fgis, "START_CELLS", [(0, 0, 10, 10)])
    monkeypatch.setattr(fgis, "START_Z", 4)

    async def fake_fetch_tile(filter_id, bbox, z):
        return [
            {"properties": {"layer": 5, "ids": [f"c{i}" for i in range(100)], "iconContent": "100"}},
            {"properties": {"layer": 5, "id": "s1"}},
        ]

    monkeypatch.setattr(fgis, "fetch_tile", fake_fetch_tile)

    seen, issues = await fgis.enumerate_region_mno_ids("f", 51)
    assert issues == []
    assert seen == {f"c{i}" for i in range(100)} | {"s1"}
    assert len(seen) == 101


# --- REGION_FED ----------------------------------------------------------------


def test_region_fed_values_in_range():
    assert REGION_FED  # непустая
    assert all(1 <= v <= 8 for v in REGION_FED.values())


def test_region_fed_known_codes():
    assert region_fed("51") == 2   # Мурманская → СЗФО
    assert region_fed("63") == 5   # Самарская → ПФО
    assert region_fed("77") == 1   # Москва → ЦФО
    assert region_fed("74") == 6   # Челябинская → УФО


def test_region_fed_unknown_is_zero():
    assert region_fed("999") == 0
    assert region_fed("") == 0


def test_region_fed_single_digit_normalized():
    # ФГИС может прислать id=1 (Адыгея) → "01" в ЮФО(3).
    assert region_fed("1") == 3
    assert region_fed("5") == 4  # Дагестан "05" → СКФО


# --- sync_regions --------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_regions_maps_id_to_code_and_preserves_operators(monkeypatch):
    """id→code=str(id), fed из карты; при update operators/active НЕ трогаются."""
    monkeypatch.setattr(
        fgis,
        "fetch_regions",
        AsyncMock(
            return_value=[
                {"id": 51, "name": "Мурманская область"},
                {"id": 63, "name": "Самарская область"},
            ]
        ),
    )

    # 51 — новый (insert); 63 — существующий (update, operators/active сохранить).
    existing_63 = Region(
        code="63", name="Старое имя", fed=0,
        operators=["ЭкоСтройРесурс"], active=False, last_sync=None,
    )
    sel_51 = MagicMock()
    sel_51.scalar_one_or_none.return_value = None
    sel_63 = MagicMock()
    sel_63.scalar_one_or_none.return_value = existing_63

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[sel_51, sel_63])
    session.add = MagicMock()

    result = await mno_sync.sync_regions(session)

    assert isinstance(result, RegionsSyncResult)
    assert result.total == 2
    assert result.created == 1
    assert result.updated == 1
    assert result.last_sync is not None

    # Существующий обновлён по name/fed/last_sync, но operators/active сохранены.
    assert existing_63.name == "Самарская область"
    assert existing_63.fed == 5
    assert existing_63.last_sync is not None
    assert existing_63.operators == ["ЭкоСтройРесурс"]
    assert existing_63.active is False

    # Новый регион вставлен с корректным кодом/округом и active=True.
    inserted = session.add.call_args.args[0]
    assert isinstance(inserted, Region)
    assert inserted.code == "51"
    assert inserted.fed == 2
    assert inserted.active is True
    assert inserted.operators == []


# --- require_superadmin --------------------------------------------------------


def _user(is_superadmin: bool) -> User:
    u = User(
        email="x@y.z", password_hash="h", fio="U", role="admin",
        status="active", is_active=True, is_superadmin=is_superadmin,
    )
    u.id = uuid4()
    return u


@pytest.mark.asyncio
async def test_require_superadmin_forbids_non_super():
    with pytest.raises(ForbiddenError):
        await require_superadmin(_user(is_superadmin=False))


@pytest.mark.asyncio
async def test_require_superadmin_allows_super():
    assert await require_superadmin(_user(is_superadmin=True)) is None


# --- Хранилище прогресса в Redis (mno_jobs) на FakeRedis -----------------------


@pytest.mark.asyncio
async def test_mno_jobs_write_read_roundtrip():
    """write_progress → read_progress восстанавливает типы (int/datetime/None)."""
    fake = FakeRedis()
    prog = mno_jobs.initial_progress("j1", "51", "Мурманская область")
    prog["discovered"] = 10
    prog["fetched"] = 8
    prog["upserted"] = 7
    prog["state"] = "done"
    prog["finished_at"] = mno_jobs.utcnow()
    await mno_jobs.write_progress(fake, "j1", prog)

    out = await mno_jobs.read_progress(fake, "j1")
    assert out is not None
    # int-поля восстановлены как int.
    assert out["discovered"] == 10 and isinstance(out["discovered"], int)
    assert out["upserted"] == 7
    # datetime-поля восстановлены из isoformat.
    assert isinstance(out["started_at"], datetime)
    assert isinstance(out["finished_at"], datetime)
    # None ↔ "" ↔ None (error пустой).
    assert out["error"] is None
    assert out["state"] == "done"
    assert out["region_code"] == "51"
    # dict годится для MnoSyncStatus(**...).
    status = MnoSyncStatus(**out)
    assert status.upserted == 7 and status.state == "done"


@pytest.mark.asyncio
async def test_mno_jobs_read_missing_is_none():
    fake = FakeRedis()
    assert await mno_jobs.read_progress(fake, "nope") is None


@pytest.mark.asyncio
async def test_mno_jobs_pointer():
    fake = FakeRedis()
    await mno_jobs.set_pointer(fake, "51", "j1")
    assert await mno_jobs.get_pointer(fake, "51") == "j1"
    assert await mno_jobs.get_pointer(fake, "63") is None


@pytest.mark.asyncio
async def test_mno_jobs_get_running_job():
    """running → снимок; завершённая/отсутствующая → None (для дедупа запусков)."""
    fake = FakeRedis()
    prog = mno_jobs.initial_progress("j1", "51", "Мурманская область")
    await mno_jobs.write_progress(fake, "j1", prog)
    await mno_jobs.set_pointer(fake, "51", "j1")

    running = await mno_jobs.get_running_job(fake, "51")
    assert running is not None and running["job_id"] == "j1"

    # Задача завершилась → get_running_job больше не отдаёт её.
    prog["state"] = "done"
    prog["finished_at"] = mno_jobs.utcnow()
    await mno_jobs.write_progress(fake, "j1", prog)
    assert await mno_jobs.get_running_job(fake, "51") is None

    # Нет указателя → None.
    assert await mno_jobs.get_running_job(fake, "63") is None


@pytest.mark.asyncio
async def test_mno_jobs_done_set():
    """mark_region_done / is_region_done — основа resume прогона «все регионы»."""
    fake = FakeRedis()
    assert await mno_jobs.is_region_done(fake, "j1", "51") is False
    await mno_jobs.mark_region_done(fake, "j1", "51")
    assert await mno_jobs.is_region_done(fake, "j1", "51") is True
    assert await mno_jobs.is_region_done(fake, "j1", "63") is False


@pytest.mark.asyncio
async def test_mno_jobs_cancel_roundtrip():
    """set_cancelled / is_cancelled — флаг отмены задачи (round-trip на FakeRedis)."""
    fake = FakeRedis()
    assert await mno_jobs.is_cancelled(fake, "j1") is False
    await mno_jobs.set_cancelled(fake, "j1")
    assert await mno_jobs.is_cancelled(fake, "j1") is True
    # Флаг именной — чужая задача не затронута.
    assert await mno_jobs.is_cancelled(fake, "j2") is False


@pytest.mark.asyncio
async def test_mno_jobs_region_synced_marker():
    """mark_region_synced / is_region_recently_synced — постоянный маркер пропуска региона."""
    fake = FakeRedis()
    assert await mno_jobs.is_region_recently_synced(fake, "51") is False
    await mno_jobs.mark_region_synced(fake, "51")
    assert await mno_jobs.is_region_recently_synced(fake, "51") is True
    assert await mno_jobs.is_region_recently_synced(fake, "63") is False


@pytest.mark.asyncio
async def test_mno_jobs_clear_job_drops_pointer():
    """clear_job снимает указатель → get_running_job=None (UI разблокирован)."""
    fake = FakeRedis()
    prog = mno_jobs.initial_progress("j1", "__all__", "Все регионы", scope="all")
    await mno_jobs.write_progress(fake, "j1", prog)
    await mno_jobs.set_pointer(fake, "__all__", "j1")
    assert await mno_jobs.get_running_job(fake, "__all__") is not None

    await mno_jobs.clear_job(fake, "__all__", "j1")
    assert await mno_jobs.get_pointer(fake, "__all__") is None
    assert await mno_jobs.get_running_job(fake, "__all__") is None


# --- Воркер (mno_worker) на FakeRedis + мок fgis/сессии ------------------------


class _FakeDBSession:
    """Поддельная AsyncSessionLocal(): async-контекст-менеджер с awaitable commit."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def commit(self):
        return None

    async def execute(self, *a, **k):
        # _existing_fgis_ids: пустой результат → в БД ничего нет, все id новые.
        res = MagicMock()
        res.all.return_value = []
        return res


def _mock_fgis_ok(monkeypatch, *, upserted=3, ids=("a", "b", "c")):
    """Общий мок ФГИС/upsert: один потоковый батч на регион, N объектов."""
    monkeypatch.setattr(mno_worker, "AsyncSessionLocal", lambda: _FakeDBSession())
    monkeypatch.setattr(fgis, "create_filter", AsyncMock(return_value="filter-uuid"))

    async def fake_enumerate(filter_id, region_id, *, on_progress=None, on_batch=None):
        if on_progress:
            on_progress(len(ids))
        if on_batch:
            await on_batch(list(ids))
        return set(ids), []

    monkeypatch.setattr(fgis, "enumerate_region_mno_ids", fake_enumerate)
    monkeypatch.setattr(
        fgis, "cluster_details", AsyncMock(return_value=[{"id": i} for i in ids])
    )
    monkeypatch.setattr(mno_sync, "_upsert_batch", AsyncMock(return_value=upserted))


@pytest.mark.asyncio
async def test_run_sync_region_done_and_progress_in_redis(monkeypatch):
    """run_sync_region: state=done, счётчики суммированы, прогресс записан в Redis."""
    _mock_fgis_ok(monkeypatch, upserted=3)

    fake = FakeRedis()
    await mno_worker.run_sync_region(fake, "j1", "51", "Мурманская область")

    prog = await mno_jobs.read_progress(fake, "j1")
    assert prog is not None
    assert prog["state"] == "done"
    assert prog["scope"] == "region"
    assert prog["discovered"] == 3
    assert prog["fetched"] == 3
    assert prog["upserted"] == 3
    assert prog["finished_at"] is not None
    assert prog["error"] is None


@pytest.mark.asyncio
async def test_run_sync_region_error_captured(monkeypatch):
    """Сбой краула → state=error, текст ошибки в прогрессе, задача закрыта (finished_at)."""
    monkeypatch.setattr(mno_worker, "AsyncSessionLocal", lambda: _FakeDBSession())
    monkeypatch.setattr(
        fgis, "create_filter", AsyncMock(side_effect=RuntimeError("ФГИС недоступна"))
    )

    fake = FakeRedis()
    await mno_worker.run_sync_region(fake, "j-err", "51", "Мурманская область")

    prog = await mno_jobs.read_progress(fake, "j-err")
    assert prog["state"] == "error"
    assert "ФГИС недоступна" in prog["error"]
    assert prog["finished_at"] is not None


@pytest.mark.asyncio
async def test_run_sync_all_sums_across_regions(monkeypatch):
    """Прогон по 2 регионам: scope=all, счётчики СУММИРУЮТСЯ, оба в done-set, done."""
    _mock_fgis_ok(monkeypatch, upserted=3)

    fake = FakeRedis()
    await mno_worker.run_sync_all(
        fake, "all-1", [["51", "Мурманская область"], ["63", "Самарская область"]]
    )

    prog = await mno_jobs.read_progress(fake, "all-1")
    assert prog["scope"] == "all"
    assert prog["state"] == "done"
    assert prog["regions_total"] == 2
    assert prog["regions_done"] == 2
    assert prog["regions_failed"] == 0
    # Накопительно по двум регионам: 3 + 3.
    assert prog["discovered"] == 6
    assert prog["fetched"] == 6
    assert prog["upserted"] == 6
    # Оба региона отмечены пройденными (для resume).
    assert await mno_jobs.is_region_done(fake, "all-1", "51")
    assert await mno_jobs.is_region_done(fake, "all-1", "63")


@pytest.mark.asyncio
async def test_run_sync_all_resume_skips_done_region(monkeypatch):
    """RESUME: регион уже в done-set (ретрай воркера) → пропущен, НЕ краулится повторно."""
    monkeypatch.setattr(mno_worker, "AsyncSessionLocal", lambda: _FakeDBSession())

    crawled: list[int] = []

    async def fake_create_filter(region_id):
        crawled.append(region_id)
        return "f"

    monkeypatch.setattr(fgis, "create_filter", fake_create_filter)

    async def fake_enumerate(filter_id, region_id, *, on_progress=None, on_batch=None):
        if on_batch:
            await on_batch(["a"])
        return {"a"}, []

    monkeypatch.setattr(fgis, "enumerate_region_mno_ids", fake_enumerate)
    monkeypatch.setattr(fgis, "cluster_details", AsyncMock(return_value=[{"id": "a"}]))
    monkeypatch.setattr(mno_sync, "_upsert_batch", AsyncMock(return_value=1))

    fake = FakeRedis()
    # 51 УЖЕ пройден в этом прогоне (эмуляция ретрая после падения воркера).
    await mno_jobs.mark_region_done(fake, "all-r", "51")

    await mno_worker.run_sync_all(
        fake, "all-r", [["51", "Мурманская область"], ["63", "Самарская область"]]
    )

    # 51 пропущен (create_filter для него не звался), краулился только 63.
    assert crawled == [63]
    prog = await mno_jobs.read_progress(fake, "all-r")
    # 51 засчитан по done-set + 63 обойдён = 2.
    assert prog["regions_done"] == 2
    assert prog["state"] == "done"


@pytest.mark.asyncio
async def test_run_sync_all_per_region_error_does_not_abort(monkeypatch):
    """Сбой ОДНОГО региона не роняет прогон: regions_failed=1, state=done, done-set без него."""
    monkeypatch.setattr(mno_worker, "AsyncSessionLocal", lambda: _FakeDBSession())
    monkeypatch.setattr(fgis, "create_filter", AsyncMock(return_value="f"))

    # 1-й регион — ок (батч записан); 2-й — краулер падает.
    calls = {"n": 0}

    async def fake_enumerate(filter_id, region_id, *, on_progress=None, on_batch=None):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("краулер упал")
        if on_progress:
            on_progress(3)
        if on_batch:
            await on_batch(["a", "b", "c"])
        return {"a", "b", "c"}, []

    monkeypatch.setattr(fgis, "enumerate_region_mno_ids", fake_enumerate)
    monkeypatch.setattr(
        fgis, "cluster_details", AsyncMock(return_value=[{"id": "a"}, {"id": "b"}, {"id": "c"}])
    )
    monkeypatch.setattr(mno_sync, "_upsert_batch", AsyncMock(return_value=3))

    fake = FakeRedis()
    await mno_worker.run_sync_all(
        fake, "all-2", [["51", "Мурманская область"], ["63", "Самарская область"]]
    )

    prog = await mno_jobs.read_progress(fake, "all-2")
    assert prog["regions_done"] == 1
    assert prog["regions_failed"] == 1
    assert prog["state"] == "done"  # прогон завершён, а не «error»
    assert "Самарская область" in prog["error"]  # ошибка помечена именем региона
    # Первый регион успел записаться до сбоя второго.
    assert prog["discovered"] == 3
    assert prog["fetched"] == 3
    assert prog["upserted"] == 3
    # В done-set только успешный регион (упавший при ретрае будет перепройден).
    assert await mno_jobs.is_region_done(fake, "all-2", "51")
    assert await mno_jobs.is_region_done(fake, "all-2", "63") is False


@pytest.mark.asyncio
async def test_run_sync_all_skips_recently_synced_region(monkeypatch):
    """ПРОПУСК НАСОВСЕМ: регион с живым region_synced-маркером не краулится (regions_done++),
    а успешно пройденный регион метится mark_region_synced."""
    monkeypatch.setattr(mno_worker, "AsyncSessionLocal", lambda: _FakeDBSession())

    crawled: list[int] = []

    async def fake_create_filter(region_id):
        crawled.append(region_id)
        return "f"

    monkeypatch.setattr(fgis, "create_filter", fake_create_filter)

    async def fake_enumerate(filter_id, region_id, *, on_progress=None, on_batch=None):
        if on_batch:
            await on_batch(["a"])
        return {"a"}, []

    monkeypatch.setattr(fgis, "enumerate_region_mno_ids", fake_enumerate)
    monkeypatch.setattr(fgis, "cluster_details", AsyncMock(return_value=[{"id": "a"}]))
    monkeypatch.setattr(mno_sync, "_upsert_batch", AsyncMock(return_value=1))

    fake = FakeRedis()
    # 51 уже синхронизирован недавно → пропустить целиком, НЕ пере-сканировать.
    await mno_jobs.mark_region_synced(fake, "51")

    await mno_worker.run_sync_all(
        fake, "all-s", [["51", "Мурманская область"], ["63", "Самарская область"]]
    )

    # 51 пропущен (create_filter для него не звался), краулился только 63.
    assert crawled == [63]
    prog = await mno_jobs.read_progress(fake, "all-s")
    # 51 засчитан по маркеру + 63 обойдён = 2.
    assert prog["regions_done"] == 2
    assert prog["state"] == "done"
    # 63 успешно пройден → теперь тоже помечен синхронизированным.
    assert await mno_jobs.is_region_recently_synced(fake, "63") is True


@pytest.mark.asyncio
async def test_run_sync_all_cancelled_on_batch_stops(monkeypatch):
    """ОТМЕНА: is_cancelled=True на _on_batch → state='cancelled', прогон прекращается сразу.

    side_effect=[False, True]: 1-я проверка (в начале региона) — не отменено, 2-я (внутри
    батча) — отменено → _CancelledSync → прогон обрывается на первом регионе."""
    _mock_fgis_ok(monkeypatch, upserted=3)
    monkeypatch.setattr(
        mno_worker, "is_cancelled", AsyncMock(side_effect=[False, True])
    )

    fake = FakeRedis()
    await mno_worker.run_sync_all(
        fake, "all-x", [["51", "Мурманская область"], ["63", "Самарская область"]]
    )

    prog = await mno_jobs.read_progress(fake, "all-x")
    assert prog["state"] == "cancelled"
    # Прогон оборван на первом регионе: ни один не досчитан, второй не тронут.
    assert prog["regions_done"] == 0
    assert prog["finished_at"] is not None
    # Первый регион НЕ помечен синхронизированным (краул прерван на батче).
    assert await mno_jobs.is_region_recently_synced(fake, "51") is False


# --- Эндпоинты (мок сервиса / Redis / arq-пула) --------------------------------


@pytest.mark.asyncio
async def test_overview_endpoint(client):
    ov = IntegrationOverview(
        regions=RegionsOverview(total=89, last_sync=None),
        mno=MnoOverview(total=1234),
        per_region=[],
    )
    with patch("app.api.v1.integration.mno_sync.overview", new=AsyncMock(return_value=ov)):
        resp = await client.get("/api/v1/integration/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["regions"]["total"] == 89
    assert body["mno"]["total"] == 1234


@pytest.mark.asyncio
async def test_regions_sync_endpoint(client, fake_session):
    result = RegionsSyncResult(total=89, created=89, updated=0, last_sync="2026-07-01T10:00:00Z")
    with patch(
        "app.api.v1.integration.mno_sync.sync_regions",
        new=AsyncMock(return_value=result),
    ):
        resp = await client.post("/api/v1/integration/regions/sync")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 89
    assert body["created"] == 89
    # роутер коммитит.
    fake_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_start_mno_sync_endpoint(client):
    """POST /mno/sync: пишет прогресс+указатель в Redis и ставит sync_region_task в очередь."""
    region = Region(code="51", name="Мурманская область", fed=2, operators=[], active=True)
    fake = FakeRedis()
    pool = AsyncMock()
    app.state.arq_pool = pool
    with patch(
        "app.api.v1.integration.mno_sync.get_region_or_404",
        new=AsyncMock(return_value=region),
    ), patch("app.api.v1.integration.get_redis", return_value=fake):
        resp = await client.post("/api/v1/integration/mno/sync", json={"region_code": "51"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["region_code"] == "51"
    assert body["state"] == "running"
    # Задача поставлена ровно раз именно как sync_region_task.
    pool.enqueue_job.assert_awaited_once()
    assert pool.enqueue_job.await_args.args[0] == "sync_region_task"
    # Указатель по региону ведёт на созданный job.
    assert await fake.get("mno:ptr:51") == body["job_id"]
    # Прогресс сразу читается из Redis (running).
    prog = await mno_jobs.read_progress(fake, body["job_id"])
    assert prog["state"] == "running" and prog["region_code"] == "51"


@pytest.mark.asyncio
async def test_start_mno_sync_dedup_returns_running(client):
    """Дедуп: по региону уже идёт задача → вернуть её без нового enqueue."""
    region = Region(code="51", name="Мурманская область", fed=2, operators=[], active=True)
    fake = FakeRedis()
    prog = mno_jobs.initial_progress("running-51", "51", "Мурманская область")
    await mno_jobs.write_progress(fake, "running-51", prog)
    await mno_jobs.set_pointer(fake, "51", "running-51")

    pool = AsyncMock()
    app.state.arq_pool = pool
    with patch(
        "app.api.v1.integration.mno_sync.get_region_or_404",
        new=AsyncMock(return_value=region),
    ), patch("app.api.v1.integration.get_redis", return_value=fake):
        resp = await client.post("/api/v1/integration/mno/sync", json={"region_code": "51"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == "running-51"
    assert body["state"] == "running"
    pool.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_mno_sync_unknown_region_404(client):
    with patch(
        "app.api.v1.integration.mno_sync.get_region_or_404",
        new=AsyncMock(side_effect=AppError("REGION_NOT_FOUND", "нет региона", status_code=404)),
    ):
        resp = await client.post("/api/v1/integration/mno/sync", json={"region_code": "99"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "REGION_NOT_FOUND"


@pytest.mark.asyncio
async def test_start_mno_sync_queue_unavailable_503(client):
    """Redis/очередь недоступны (arq_pool=None) → 503 QUEUE_UNAVAILABLE, а не 500."""
    region = Region(code="51", name="Мурманская область", fed=2, operators=[], active=True)
    app.state.arq_pool = None  # пул не поднят (Redis лежит)
    with patch(
        "app.api.v1.integration.mno_sync.get_region_or_404",
        new=AsyncMock(return_value=region),
    ):
        resp = await client.post("/api/v1/integration/mno/sync", json={"region_code": "51"})
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "QUEUE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_mno_sync_status_by_job_id(client):
    """GET status?job_id читает снимок из Redis."""
    fake = FakeRedis()
    prog = mno_jobs.initial_progress("job-123", "51", "Мурманская область")
    prog["state"] = "done"
    prog["discovered"] = 42
    prog["fetched"] = 42
    prog["upserted"] = 40
    prog["finished_at"] = mno_jobs.utcnow()
    await mno_jobs.write_progress(fake, "job-123", prog)

    with patch("app.api.v1.integration.get_redis", return_value=fake):
        resp = await client.get("/api/v1/integration/mno/sync/status?job_id=job-123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "done"
    assert body["discovered"] == 42
    assert body["upserted"] == 40


@pytest.mark.asyncio
async def test_mno_sync_status_by_region_code_via_pointer(client):
    """GET status?region_code=__all__ находит последнюю задачу через указатель."""
    fake = FakeRedis()
    prog = mno_jobs.initial_progress(
        "all-9", "__all__", "Все регионы", scope="all", regions_total=3
    )
    await mno_jobs.write_progress(fake, "all-9", prog)
    await mno_jobs.set_pointer(fake, "__all__", "all-9")

    with patch("app.api.v1.integration.get_redis", return_value=fake):
        resp = await client.get("/api/v1/integration/mno/sync/status?region_code=__all__")
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == "all-9"
    assert body["scope"] == "all"
    assert body["regions_total"] == 3


@pytest.mark.asyncio
async def test_mno_sync_status_not_found_404(client):
    fake = FakeRedis()
    with patch("app.api.v1.integration.get_redis", return_value=fake):
        resp = await client.get("/api/v1/integration/mno/sync/status?job_id=missing")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_cancel_mno_sync_cancels_running(client):
    """POST /mno/sync/cancel: есть указатель → cancelled=true, флаг отмены выставлен,
    снимок помечен cancelled, указатель снят (get_running_job=None → UI разблокирован)."""
    fake = FakeRedis()
    prog = mno_jobs.initial_progress(
        "all-c", "__all__", "Все регионы", scope="all", regions_total=3
    )
    await mno_jobs.write_progress(fake, "all-c", prog)
    await mno_jobs.set_pointer(fake, "__all__", "all-c")

    with patch("app.api.v1.integration.get_redis", return_value=fake):
        resp = await client.post(
            "/api/v1/integration/mno/sync/cancel", json={"scope": "all"}
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["cancelled"] is True
    assert body["job_id"] == "all-c"
    # Флаг отмены выставлен — воркер прекратит краул на ближайшем батче.
    assert await mno_jobs.is_cancelled(fake, "all-c") is True
    # Снимок сразу помечен cancelled (+ finished_at).
    prog2 = await mno_jobs.read_progress(fake, "all-c")
    assert prog2["state"] == "cancelled"
    assert prog2["finished_at"] is not None
    # Указатель снят → активной задачи по ключу больше нет.
    assert await mno_jobs.get_pointer(fake, "__all__") is None
    assert await mno_jobs.get_running_job(fake, "__all__") is None


@pytest.mark.asyncio
async def test_cancel_mno_sync_no_job_returns_false(client):
    """POST /mno/sync/cancel без активной задачи по ключу → cancelled=false, job_id=null."""
    fake = FakeRedis()
    with patch("app.api.v1.integration.get_redis", return_value=fake):
        resp = await client.post(
            "/api/v1/integration/mno/sync/cancel", json={"scope": "all"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cancelled"] is False
    assert body["job_id"] is None


# --- Синхронизация МНО по ВСЕМ регионам разом ----------------------------------


@pytest.mark.asyncio
async def test_start_mno_sync_all_empty_catalog_400(client, fake_session):
    """Пустой справочник регионов → 400 NO_REGIONS (сначала синхронизируй регионы)."""
    sel = MagicMock()
    sel.all.return_value = []
    fake_session.execute = AsyncMock(return_value=sel)

    resp = await client.post("/api/v1/integration/mno/sync-all")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "NO_REGIONS"


@pytest.mark.asyncio
async def test_start_mno_sync_all_queue_unavailable_503(client, fake_session):
    """Непустой справочник, но очередь недоступна (arq_pool=None) → 503."""
    sel = MagicMock()
    sel.all.return_value = [("51", "Мурманская область")]
    fake_session.execute = AsyncMock(return_value=sel)

    app.state.arq_pool = None
    resp = await client.post("/api/v1/integration/mno/sync-all")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "QUEUE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_start_mno_sync_all_endpoint(client, fake_session):
    """Непустой справочник → 200, задача region_code='__all__', sync_all_task в очереди."""
    sel = MagicMock()
    sel.all.return_value = [("51", "Мурманская область"), ("63", "Самарская область")]
    fake_session.execute = AsyncMock(return_value=sel)

    fake = FakeRedis()
    pool = AsyncMock()
    app.state.arq_pool = pool
    with patch("app.api.v1.integration.get_redis", return_value=fake):
        resp = await client.post("/api/v1/integration/mno/sync-all")

    assert resp.status_code == 200
    body = resp.json()
    assert body["region_code"] == "__all__"
    assert body["state"] == "running"
    pool.enqueue_job.assert_awaited_once()
    assert pool.enqueue_job.await_args.args[0] == "sync_all_task"
    # Указатель "__all__" ведёт на созданный job.
    assert await fake.get("mno:ptr:__all__") == body["job_id"]


@pytest.mark.asyncio
async def test_start_mno_sync_all_dedup_returns_running(client, fake_session):
    """Дедуп прогона «все регионы»: уже идёт → вернуть его без enqueue."""
    sel = MagicMock()
    sel.all.return_value = [("51", "Мурманская область")]
    fake_session.execute = AsyncMock(return_value=sel)

    fake = FakeRedis()
    prog = mno_jobs.initial_progress(
        "running-all", "__all__", "Все регионы", scope="all", regions_total=1
    )
    await mno_jobs.write_progress(fake, "running-all", prog)
    await mno_jobs.set_pointer(fake, "__all__", "running-all")

    pool = AsyncMock()
    app.state.arq_pool = pool
    with patch("app.api.v1.integration.get_redis", return_value=fake):
        resp = await client.post("/api/v1/integration/mno/sync-all")

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == "running-all"
    assert body["region_code"] == "__all__"
    assert body["state"] == "running"
    pool.enqueue_job.assert_not_awaited()


# --- Детали МНО: sidebar/object как документированный фолбэк --------------------


def test_object_to_flat_maps_nested_sidebar_object():
    """Вложенный ответ sidebar/object (док §3) → плоская форма sidebar/cluster."""
    obj = {
        "id": "7d257019",
        "name": "Контейнерная площадка",
        "registryNumber": "0000217-03",
        "location": {
            "areaName": "Курумканский муниципальный район",
            "populationName": "Сельское поселение Элэсун",
            "address": "ул. Ленина, 52",
            "coordinates": {"latitude": 54.035044, "longitude": 110.097837},
        },
    }
    flat = fgis._object_to_flat(obj)
    assert flat == {
        "id": "7d257019",
        "name": "Контейнерная площадка",
        "registryNumber": "0000217-03",
        "area": "Курумканский муниципальный район",
        "population": "Сельское поселение Элэсун",
        "address": "ул. Ленина, 52",
        "location": {"latitude": 54.035044, "longitude": 110.097837},
    }


@pytest.mark.asyncio
async def test_cluster_details_falls_back_to_sidebar_object(monkeypatch):
    """Если батч sidebar/cluster недоступен — cluster_details деградирует на
    документированный sidebar/object по одному id и отдаёт ту же плоскую форму."""

    class _BoomClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise httpx.ConnectError("batch недоступен")

    monkeypatch.setattr(fgis.httpx, "AsyncClient", _BoomClient)

    async def _fake_object(mno_id):
        return {
            "id": mno_id,
            "name": "Площадка",
            "registryNumber": "R-1",
            "location": {
                "areaName": "Район",
                "populationName": "Село",
                "address": "ул. Тест, 1",
                "coordinates": {"latitude": 1.5, "longitude": 2.5},
            },
        }

    monkeypatch.setattr(fgis, "sidebar_object", _fake_object)

    out = await fgis.cluster_details(["id-1", "id-2"], region_id=3)
    assert len(out) == 2
    assert out[0]["name"] == "Площадка"
    assert out[0]["address"] == "ул. Тест, 1"
    assert out[0]["area"] == "Район"
    assert out[0]["location"] == {"latitude": 1.5, "longitude": 2.5}


# --- id-level skip: дешёвое возобновление (не тянем детали уже записанных МНО) --------


@pytest.mark.asyncio
async def test_existing_fgis_ids_returns_present():
    from app.services import mno_worker

    res = MagicMock()
    res.all.return_value = [("a",), ("c",), (None,)]  # None-строки отфильтровываются
    session = AsyncMock()
    session.execute = AsyncMock(return_value=res)

    got = await mno_worker._existing_fgis_ids(session, ["a", "b", "c"])
    assert got == {"a", "c"}

    # Пустой вход → пустой набор, без обращения к БД.
    session.execute.reset_mock()
    assert await mno_worker._existing_fgis_ids(session, []) == set()
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_crawl_region_skips_existing_fgis_ids(monkeypatch):
    """_crawl_region тянет детали ТОЛЬКО для новых id — уже записанные пропускает."""
    from app.services import mno_worker

    async def fake_enumerate(filter_id, region_id, *, on_progress=None, on_batch=None):
        on_progress(4)
        await on_batch(["a", "b", "c", "d"])
        return set(), []

    monkeypatch.setattr(fgis, "create_filter", AsyncMock(return_value="fid"))
    monkeypatch.setattr(fgis, "enumerate_region_mno_ids", fake_enumerate)
    # В БД уже есть "a" и "c" → детали тянем только для "b","d".
    monkeypatch.setattr(
        mno_worker, "_existing_fgis_ids", AsyncMock(return_value={"a", "c"})
    )
    monkeypatch.setattr(mno_worker, "write_progress", AsyncMock())

    cluster_calls: list = []

    async def fake_cluster(ids, region_id):
        cluster_calls.append(list(ids))
        return [{"id": i} for i in ids]

    monkeypatch.setattr(fgis, "cluster_details", fake_cluster)
    monkeypatch.setattr(mno_sync, "_upsert_batch", AsyncMock(return_value=2))

    session = AsyncMock()
    prog = {"discovered": 0, "fetched": 0, "upserted": 0}
    # FakeRedis: is_cancelled в _on_batch читает redis.get → отмены нет (None), батч идёт.
    await mno_worker._crawl_region(FakeRedis(), "job-1", prog, session, 22)

    assert cluster_calls == [["b", "d"]]  # только новые id
    assert prog["fetched"] == 2
    assert prog["upserted"] == 2
    assert prog["discovered"] == 4  # обнаружено считаются ВСЕ (для прогресса)


# --- авто-детект зависшей задачи (heartbeat updated_at → авто-разлочка UI) ------


def test_is_stale_by_updated_at():
    from datetime import timedelta

    assert mno_jobs.is_stale({"updated_at": mno_jobs.utcnow()}) is False
    old = mno_jobs.utcnow() - timedelta(seconds=mno_jobs.STALE_SECONDS + 60)
    assert mno_jobs.is_stale({"updated_at": old}) is True
    # Снимок без heartbeat (старый/битый) — считаем зависшим.
    assert mno_jobs.is_stale({"updated_at": None}) is True
    assert mno_jobs.is_stale({}) is True


@pytest.mark.asyncio
async def test_get_running_job_ignores_stale():
    from datetime import timedelta

    r = FakeRedis()
    await mno_jobs.set_pointer(r, "__all__", "job-live")
    await mno_jobs.write_progress(
        r,
        "job-live",
        mno_jobs.initial_progress(
            "job-live", "__all__", "Все регионы", scope="all", regions_total=5
        ),
    )
    # Живая running-задача (свежий heartbeat) → отдаётся (дедуп сработает).
    assert (await mno_jobs.get_running_job(r, "__all__")) is not None

    # Состарим heartbeat вручную → get_running_job вернёт None → UI сам разлочится.
    stale = mno_jobs.utcnow() - timedelta(seconds=mno_jobs.STALE_SECONDS + 60)
    r.hashes["mno:job:job-live"]["updated_at"] = stale.isoformat()
    assert (await mno_jobs.get_running_job(r, "__all__")) is None
