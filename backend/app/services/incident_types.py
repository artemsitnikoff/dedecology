"""Справочник типов инцидента (10 значений, порядок фиксирован).

Модуль-константа: статичные данные, в БД не хранятся (меняются раз в эпоху) —
по образцу services/federal_districts.py. В инциденте хранится КОД типа
(String, напр. «fire»); русская подпись резолвится по этому справочнику.
Используется публичной формой волонтёра (обязательный дропдаун), эндпоинтом
GET /intake/incident-types и админкой (резолв кода → подписи).
"""

# Порядок фиксирован (как показывается в дропдауне формы): код → русская подпись.
INCIDENT_TYPES: list[dict] = [
    {"code": "no_access", "label": "Отсутствует доступ к МНО"},
    {"code": "blocked_access", "label": "Проезд заблокирован автомобилем"},
    {"code": "no_container", "label": "Контейнер отсутствует"},
    {"code": "fire", "label": "Возгорание в контейнере"},
    {
        "code": "non_tko_in_container",
        "label": "В контейнере находятся отходы, не относящиеся к ТКО",
    },
    {"code": "damaged_container", "label": "Контейнер поврежден"},
    {"code": "waste_nearby", "label": "Наличие отходов рядом с МНО"},
    {
        "code": "non_tko_on_site",
        "label": "На контейнерной площадке вне контейнеров зафиксированы отходы, "
        "не относящиеся к ТКО",
    },
    {"code": "overflow", "label": "Зафиксировано переполнение контейнеров"},
    {"code": "other", "label": "Иное"},
]

# code → label для быстрого резолва подписи и проверки валидности.
_LABEL_BY_CODE: dict[str, str] = {t["code"]: t["label"] for t in INCIDENT_TYPES}


def is_valid_incident_type(code: str) -> bool:
    """True, если code — один из известных кодов типа инцидента (иначе, вкл. ""/None → False)."""
    return code in _LABEL_BY_CODE


def incident_type_label(code: str | None) -> str:
    """Русская подпись типа по коду; "" для None/пустого/неизвестного кода."""
    if not code:
        return ""
    return _LABEL_BY_CODE.get(code, "")


def list_incident_types() -> list[dict]:
    """Справочник как список [{code, label}] (для GET /intake/incident-types и дропдаунов)."""
    return list(INCIDENT_TYPES)
