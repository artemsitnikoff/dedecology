"""Гео-утилиты: разбор текстовых координат «lat, lon» и bbox видимой области карты.

Координаты у инцидентов и МНО хранятся строкой «широта, долгота» — для быстрого
bbox-фильтра на карте заведены отдельные числовые колонки lat/lon (миграция 0009).
Здесь единая НЕ бросающая логика их получения из текста и разбора bbox запроса.
"""


def parse_latlon(coords: str | None) -> tuple[float | None, float | None]:
    """«lat, lon» текстом → (lat, lon) как float; битый/пустой вход → (None, None).

    Никогда не бросает: любое не-числовое/неполное значение → (None, None) — такие
    точки на карту не попадают (числовые колонки остаются NULL). Пробелы вокруг чисел
    допускаются («53.2, 50.6» и «53.2,50.6» эквивалентны).
    """
    if not coords:
        return None, None
    parts = coords.split(",")
    if len(parts) != 2:
        return None, None
    try:
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
    except (ValueError, TypeError):
        return None, None
    return lat, lon


def parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    """«minLat,minLon,maxLat,maxLon» → (minLat, minLon, maxLat, maxLon) или None.

    Устойчив к мусору: всё, что не 4 числа через запятую, → None (эндпоинт трактует
    это как «bbox не задан» и отдаёт глобальный кадр по фильтрам). Не бросает.
    """
    if not bbox:
        return None
    parts = bbox.split(",")
    if len(parts) != 4:
        return None
    try:
        min_lat = float(parts[0].strip())
        min_lon = float(parts[1].strip())
        max_lat = float(parts[2].strip())
        max_lon = float(parts[3].strip())
    except (ValueError, TypeError):
        return None
    return min_lat, min_lon, max_lat, max_lon
