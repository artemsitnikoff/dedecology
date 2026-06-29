"""Тесты нормализации региона/города (app.services.addr_norm) + проверка, что
пути приёма (resolve_address, create_incident_from_form) сохраняют УЖЕ
нормализованный регион при мокнутой сокращённой DaData-форме.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.addr_norm import normalize_city, normalize_region

# --------------------------------------------------------------------------- #
# normalize_region — таблица вход → ожидаемый выход                            #
# --------------------------------------------------------------------------- #

_REGION_CASES = [
    # «обл» / «обл.» → «область»
    ("Мурманская обл", "Мурманская область"),
    ("Мурманская обл.", "Мурманская область"),
    ("Челябинская обл", "Челябинская область"),
    ("Самарская обл", "Самарская область"),
    ("Нижегородская обл", "Нижегородская область"),
    # «Респ …» / «респ …» → «Республика …»
    ("Респ Татарстан", "Республика Татарстан"),
    ("респ Татарстан", "Республика Татарстан"),
    ("Респ. Саха (Якутия)", "Республика Саха (Якутия)"),
    ("Респ.Коми", "Республика Коми"),
    # «… Аобл» → «… автономная область»
    ("Еврейская Аобл", "Еврейская автономная область"),
    ("Еврейская аобл", "Еврейская автономная область"),
    # «… АО» / «… а.о.» → «… автономный округ»
    ("Ханты-Мансийский АО", "Ханты-Мансийский автономный округ"),
    ("Ямало-Ненецкий АО", "Ямало-Ненецкий автономный округ"),
    ("Ненецкий а.о.", "Ненецкий автономный округ"),
    ("Чукотский АО", "Чукотский автономный округ"),
    # «г Москва» / «г. Москва» / «г.Москва» → «Москва» (срез типа «город»)
    ("г Москва", "Москва"),
    ("г. Москва", "Москва"),
    ("г.Москва", "Москва"),
    ("г Санкт-Петербург", "Санкт-Петербург"),
    ("г Севастополь", "Севастополь"),
    # «… край» и уже-полные формы — без изменений
    ("Краснодарский край", "Краснодарский край"),
    ("Алтайский край", "Алтайский край"),
    ("Мурманская область", "Мурманская область"),
    ("Республика Татарстан", "Республика Татарстан"),
    ("Москва", "Москва"),
    ("Санкт-Петербург", "Санкт-Петербург"),
    ("Ханты-Мансийский автономный округ", "Ханты-Мансийский автономный округ"),
    ("Еврейская автономная область", "Еврейская автономная область"),
    # имена-«ловушки»: «Гремячинск» не должен потерять «г», «Новгород» — «обл»
    ("Гремячинская область", "Гремячинская область"),
    # схлопывание лишних пробелов
    ("Мурманская   обл", "Мурманская область"),
    ("  Респ   Татарстан  ", "Республика Татарстан"),
    # пусто
    ("", ""),
]


@pytest.mark.parametrize("raw, expected", _REGION_CASES)
def test_normalize_region_cases(raw, expected):
    assert normalize_region(raw) == expected


@pytest.mark.parametrize("raw, expected", _REGION_CASES)
def test_normalize_region_idempotent(raw, expected):
    """Повторный вызов на уже нормализованном значении ничего не меняет."""
    once = normalize_region(raw)
    assert once == expected
    assert normalize_region(once) == once


def test_normalize_region_none_returns_empty():
    assert normalize_region(None) == ""  # type: ignore[arg-type]


def test_normalize_region_full_forms_untouched():
    """Полные формы и «… край» проходят без изменений (регресс на over-normalize)."""
    for full in (
        "Самарская область",
        "Республика Татарстан",
        "Краснодарский край",
        "Москва",
        "Ханты-Мансийский автономный округ",
    ):
        assert normalize_region(full) == full


# --------------------------------------------------------------------------- #
# normalize_city — консервативная нормализация                                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("город Кинель", "г Кинель"),
        ("Город Самара", "г Самара"),
        ("г Кинель", "г Кинель"),          # тип-аббревиатуру не трогаем
        ("г. Кинель", "г. Кинель"),        # точку префикса не трогаем
        ("Кинель", "Кинель"),              # без типа — оставляем
        ("пгт Усть-Кинельский", "пгт Усть-Кинельский"),
        ("с. Сырейка", "с. Сырейка"),
        ("Великий   Новгород", "Великий Новгород"),  # «город» внутри слова не трогаем
        ("Нижний Новгород", "Нижний Новгород"),
        ("", ""),
    ],
)
def test_normalize_city_cases(raw, expected):
    assert normalize_city(raw) == expected


def test_normalize_city_idempotent():
    for raw in ("город Кинель", "г Кинель", "Великий Новгород", "пгт Усть-Кинельский"):
        once = normalize_city(raw)
        assert normalize_city(once) == once


def test_normalize_city_none_returns_empty():
    assert normalize_city(None) == ""  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Интеграция: пути приёма сохраняют УЖЕ нормализованный регион                 #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_resolve_address_normalizes_short_region_from_geocode():
    """geocode/Clean вернули сокращённый region_with_type → в результате полная форма."""
    from app.services import intake

    ai = {
        "region": "Мурманская область",
        "city": "Мурманск",
        "street": "Ленина, 5",
        "coords": "",
        "time": "",
    }
    geocoded = {  # DaData-стиль: сокращённый тип субъекта
        "region": "Мурманская обл",
        "city": "г Мурманск",
        "street": "ул Ленина, 5",
        "coords": "68.97, 33.07",
        "geo_lat": "68.97",
        "geo_lon": "33.07",
    }
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=ai)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=geocoded)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        region, city, street, coords = await intake.resolve_address("Мурманск Ленина 5")

    assert region == "Мурманская область"  # нормализовано из «Мурманская обл»
    assert city == "г Мурманск"            # тип пункта оставлен как есть
    assert coords == "68.97, 33.07"


@pytest.mark.asyncio
async def test_resolve_address_normalizes_respublika_ai_only():
    """ai-only путь (DaData недоступна): «Респ Татарстан» из AI → «Республика Татарстан»."""
    from app.services import intake

    ai = {
        "region": "Респ Татарстан",
        "city": "Казань",
        "street": "Чистопольская, 61",
        "coords": "55.82, 49.11",
        "time": "",
    }
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=ai)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        region, city, street, coords = await intake.resolve_address("Казань Чистопольская 61")

    assert region == "Республика Татарстан"
    assert city == "Казань"


@pytest.mark.asyncio
async def test_create_incident_from_form_normalizes_region(fake_session):
    """full_address с сокращённым регионом → инцидент хранит полную форму региона."""
    from app.services.intake import create_incident_from_form

    fake_session.add = MagicMock()
    incident = await create_incident_from_form(
        fake_session,
        {"full_address": "Мурманская обл, г Мурманск, ул Ленина, 5", "fio": "Тест"},
    )
    assert incident.region == "Мурманская область"  # «обл» → «область»
    assert incident.city == "г Мурманск"
