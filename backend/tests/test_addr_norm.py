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
async def test_resolve_address_no_ai_geocodes_via_free_suggest():
    """БЕЗ AI (ai_parse_incident → None) шаблонный адрес ВСЁ РАВНО геокодится бесплатными
    Подсказками, а не уходит в эвристику с пустыми coords. Регресс: на проде без «нейронки»
    бот отвечал «Не удалось определить адрес» — координаты в фолбэке не добывались (звался только
    платный Clean = 403), теперь сперва бесплатный geocode_address."""
    from app.services import intake

    geocoded = {
        "region": "Тюменская обл",
        "city": "г Тюмень",
        "street": "ул Новосёлов, 92",
        "coords": "57.15, 65.53",
        "geo_lat": "57.15",
        "geo_lon": "65.53",
    }
    geo_mock = AsyncMock(return_value=geocoded)
    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=None)  # AI выключен
    ), patch("app.services.intake.geocode_address", new=geo_mock), patch(
        "app.services.intake.clean_address", new=AsyncMock(return_value=None)
    ):
        region, city, street, coords = await intake.resolve_address(
            "Тюменская область, г.Тюмень, ул.Новоселов, 92. Время 19:22"
        )

    assert coords == "57.15, 65.53"  # координаты добыты БЕЗ AI
    assert region == "Тюменская область"  # нормализовано из «Тюменская обл»
    # геокод вызван с адресом БЕЗ хвоста «Время 19:22»
    geo_mock.assert_awaited_once()
    query = geo_mock.await_args.args[0]
    assert "Время" not in query and "19:22" not in query
    assert query.endswith("92")


@pytest.mark.asyncio
async def test_resolve_address_no_ai_no_dadata_falls_to_heuristic():
    """БЕЗ AI и без DaData (geocode+clean → None) → эвристика, coords пустые, без падений."""
    from app.services import intake

    with patch(
        "app.services.intake.ai_parse_incident", new=AsyncMock(return_value=None)
    ), patch(
        "app.services.intake.geocode_address", new=AsyncMock(return_value=None)
    ), patch("app.services.intake.clean_address", new=AsyncMock(return_value=None)):
        region, city, street, coords = await intake.resolve_address(
            "Тюменская область, г.Тюмень, ул.Новоселов, 92. Время 19:22"
        )
    assert coords == ""
    assert region  # эвристика хоть что-то положила в регион (не упала)


def test_strip_time_suffix():
    """Отсечение хвостового «Время ЧЧ:ММ» / «ЧЧ:ММ»; дом и адрес сохраняются; нет времени → как есть."""
    from app.services.intake import _strip_time_suffix

    assert (
        _strip_time_suffix("Тюменская область, г.Тюмень, ул.Новоселов, 92. Время 19:22")
        == "Тюменская область, г.Тюмень, ул.Новоселов, 92"
    )
    assert _strip_time_suffix("Самара, Победы 10, 9.05") == "Самара, Победы 10"
    assert _strip_time_suffix("Казань, Баумана 1") == "Казань, Баумана 1"


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
