"""Справочник федеральных округов РФ (нумерация ФГИС, 1..8).

Модуль-константа: статичные данные, в БД не хранятся (меняются раз в эпоху).
Используется регионами для расшифровки fed → {code, name} и эндпоинтом
GET /federal-districts.
"""

# id округа (ФГИС) → {code (аббревиатура), name (без слова «федеральный округ»)}
FEDERAL_DISTRICTS: dict[int, dict[str, str]] = {
    1: {"code": "ЦФО", "name": "Центральный"},
    2: {"code": "СЗФО", "name": "Северо-Западный"},
    3: {"code": "ЮФО", "name": "Южный"},
    4: {"code": "СКФО", "name": "Северо-Кавказский"},
    5: {"code": "ПФО", "name": "Приволжский"},
    6: {"code": "УФО", "name": "Уральский"},
    7: {"code": "СФО", "name": "Сибирский"},
    8: {"code": "ДФО", "name": "Дальневосточный"},
}


def get_federal_district(fed_id: int) -> dict[str, str] | None:
    """Округ по id или None, если такого нет."""
    return FEDERAL_DISTRICTS.get(fed_id)


def fed_code(fed_id: int) -> str:
    """Аббревиатура округа ("ЦФО") или "" для неизвестного id."""
    d = FEDERAL_DISTRICTS.get(fed_id)
    return d["code"] if d else ""


def fed_name(fed_id: int) -> str:
    """Имя округа ("Центральный") или "" для неизвестного id."""
    d = FEDERAL_DISTRICTS.get(fed_id)
    return d["name"] if d else ""


def list_federal_districts() -> list[dict]:
    """Справочник как список [{id, code, name}] (для GET /federal-districts)."""
    return [
        {"id": fid, "code": d["code"], "name": d["name"]}
        for fid, d in FEDERAL_DISTRICTS.items()
    ]
