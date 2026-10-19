"""Охранные тесты: лимиты фото (ПУНКТ 4) и приоритет координат (ПУНКТ 3).

Офлайн, без БД. Фото — проверяем гейт количества в _decode_uploads (отбивается ДО
записи в БД); приоритет координат — resolve_address с замоканными AI/DaData.
"""

from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from app.core.errors import ValidationError
from app.services import intake


def _jpeg_bytes(size=(64, 48), color=(0, 120, 0)) -> bytes:
    """Маленький, но настоящий JPEG (Pillow декодирует) — пере-кодирование требует
    реального изображения, сырой \\xff\\xd8\\xff не годится."""
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


class _FakeUpload:
    """Минимальный UploadFile-подобный объект: async read + filename."""

    def __init__(self, data: bytes, filename: str = "0.jpg"):
        self._buf = BytesIO(data)
        self.filename = filename
        self.content_type = "image/jpeg"

    async def read(self, size: int = -1) -> bytes:
        return self._buf.read(size)


# --- ПУНКТ 4: лимит фото 6 → 10 ------------------------------------------------


def test_max_photos_constant_is_ten():
    """Утверждённое число: _MAX_PHOTOS == 10 (было 6)."""
    assert intake._MAX_PHOTOS == 10


@pytest.mark.asyncio
async def test_decode_uploads_accepts_ten_photos():
    """Ровно 10 фото — проходят (новый лимит), все декодируются."""
    uploads = [_FakeUpload(_jpeg_bytes(), filename=f"{i}.jpg") for i in range(10)]
    decoded = await intake._decode_uploads(uploads)
    assert len(decoded) == 10


@pytest.mark.asyncio
async def test_decode_uploads_rejects_eleventh_photo():
    """11-е фото режется → ValidationError (отбой до записи в БД)."""
    uploads = [_FakeUpload(_jpeg_bytes(), filename=f"{i}.jpg") for i in range(11)]
    with pytest.raises(ValidationError):
        await intake._decode_uploads(uploads)


# --- ПУНКТ 3: приоритет координат — AI важнее геокода DaData -------------------


@pytest.mark.asyncio
async def test_resolve_address_prefers_ai_coords_over_geocode():
    """При непустых координатах AND И непустом геокоде DaData выбираются координаты AI
    (промпт эмитит coords только при реальных числах в тексте → они авторитетнее
    геокода адресной строки). Адресные поля при этом остаются из DaData."""
    ai = {
        "region": "Самарская область",
        "city": "Кинель",
        "street": "ул. Маяковского, 41",
        "coords": "53.231410, 50.166820",  # координаты из текста (AI)
    }
    geocoded = {  # DaData дала СВОИ координаты (другие) + стандартизировала поля
        "region": "Самарская область",
        "city": "г Кинель",
        "street": "ул Маяковского, д 41",
        "coords": "53.200000, 50.600000",
    }
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=ai)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=geocoded)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        region, city, street, coords = await intake.resolve_address(
            "Кинель, Маяковского 41, 53.231410, 50.166820"
        )
    # Координаты — из AI, НЕ из геокода.
    assert coords == "53.231410, 50.166820"
    # Адресные поля остались из DaData (стандартизация).
    assert region == "Самарская область"


@pytest.mark.asyncio
async def test_resolve_address_falls_back_to_geocode_coords_when_ai_empty():
    """AI не дал координат (пусто) → берётся геокод DaData (фолбэк сохранён)."""
    ai = {
        "region": "Самарская область",
        "city": "Кинель",
        "street": "ул. Маяковского, 41",
        "coords": "",  # AI координат не нашёл
    }
    geocoded = {
        "region": "Самарская область",
        "city": "г Кинель",
        "street": "ул Маяковского, д 41",
        "coords": "53.200000, 50.600000",
    }
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=ai)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=geocoded)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        _, _, _, coords = await intake.resolve_address("Кинель, Маяковского 41")
    assert coords == "53.200000, 50.600000"
