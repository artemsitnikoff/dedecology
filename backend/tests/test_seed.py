"""Тесты идемпотентности сид-функций регионов/МНО — офлайн (session мокается)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.seed import DEMO_MNO, DEMO_REGIONS, seed_mno, seed_regions


def _session_with_count(count: int) -> AsyncMock:
    """AsyncMock-сессия, у которой count(...) → заданное число."""
    res = MagicMock()
    res.scalar_one.return_value = count
    session = AsyncMock()
    session.execute = AsyncMock(return_value=res)
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_seed_regions_inserts_when_empty():
    session = _session_with_count(0)
    await seed_regions(session)
    assert session.add.call_count == len(DEMO_REGIONS) == 8


@pytest.mark.asyncio
async def test_seed_regions_idempotent_when_present():
    session = _session_with_count(8)
    await seed_regions(session)
    assert session.add.call_count == 0


@pytest.mark.asyncio
async def test_seed_mno_inserts_when_empty():
    session = _session_with_count(0)
    await seed_mno(session)
    assert session.add.call_count == len(DEMO_MNO) == 15


@pytest.mark.asyncio
async def test_seed_mno_idempotent_when_present():
    session = _session_with_count(15)
    await seed_mno(session)
    assert session.add.call_count == 0


def test_seed_mno_split_synced_manual():
    """Контракт (по data.js): 12 synced (fgis_id+sync_date) + 3 вручную (synced=False, sync_date пуст)."""
    synced = [m for m in DEMO_MNO if m["synced"]]
    manual = [m for m in DEMO_MNO if not m["synced"]]
    assert len(synced) == 12
    assert len(manual) == 3
    for m in synced:
        assert m["fgisId"] and m["syncDate"]
    for m in manual:
        assert m["syncDate"] is None


def test_seed_regions_match_contract():
    """8 регионов с кодами/округами по контракту."""
    by_code = {r["code"]: r for r in DEMO_REGIONS}
    assert set(by_code) == {"63", "77", "78", "16", "52", "53", "66", "73"}
    assert by_code["63"]["fed"] == 5
    assert by_code["77"]["fed"] == 1
    assert by_code["73"]["name"] == "Ульяновская область" and by_code["73"]["fed"] == 5


def test_seed_mno_region_codes_within_seeded_regions():
    """Все region_code сидовых МНО есть среди сидовых регионов."""
    region_codes = {r["code"] for r in DEMO_REGIONS}
    assert {m["region_code"] for m in DEMO_MNO} <= region_codes
