"""Тесты гео-утилит parse_latlon / parse_bbox (офлайн, без БД)."""

import pytest

from app.services.geo import parse_bbox, parse_latlon


# --- parse_latlon --------------------------------------------------------------


@pytest.mark.parametrize(
    "coords,expected",
    [
        ("53.231410, 50.166820", (53.231410, 50.166820)),  # валид с пробелом
        ("53.2,50.6", (53.2, 50.6)),                         # валид без пробела
        ("-53.2, -50.6", (-53.2, -50.6)),                    # отрицательные
        ("  53.2 ,  50.6  ", (53.2, 50.6)),                  # обрамляющие пробелы
        ("53, 50", (53.0, 50.0)),                            # целые → float
    ],
)
def test_parse_latlon_valid(coords, expected):
    """Валидная пара «lat, lon» → (float, float)."""
    assert parse_latlon(coords) == expected


@pytest.mark.parametrize(
    "coords",
    [
        "",                      # пусто
        None,                    # None
        "   ",                   # только пробелы
        "53.2",                  # одно число
        "53.2, 50.6, 10",        # три числа
        "abc, def",              # не числа
        "53.2, ",                # вторая часть пуста
        "широта, долгота",       # мусор
    ],
)
def test_parse_latlon_invalid(coords):
    """Битый/пустой вход → (None, None), без исключений."""
    assert parse_latlon(coords) == (None, None)


# --- parse_bbox ----------------------------------------------------------------


def test_parse_bbox_valid():
    """4 числа через запятую → кортеж (minLat, minLon, maxLat, maxLon)."""
    assert parse_bbox("53.0,50.0,54.0,51.0") == (53.0, 50.0, 54.0, 51.0)


def test_parse_bbox_valid_with_spaces_and_negatives():
    """Пробелы и отрицательные значения допускаются."""
    assert parse_bbox(" -53.5 , 50.0 , -52.0 , 51.5 ") == (-53.5, 50.0, -52.0, 51.5)


@pytest.mark.parametrize(
    "bbox",
    [
        "",                       # пусто
        None,                     # None
        "53.0,50.0,54.0",         # 3 числа
        "53.0,50.0,54.0,51.0,1",  # 5 чисел
        "a,b,c,d",                # не числа
        "53.0 50.0 54.0 51.0",    # без запятых
    ],
)
def test_parse_bbox_invalid(bbox):
    """Битый/пустой bbox → None (эндпоинт трактует как «не задан»)."""
    assert parse_bbox(bbox) is None
