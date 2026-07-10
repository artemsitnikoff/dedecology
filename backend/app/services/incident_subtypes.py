"""Фиксированный справочник подтипов инцидента.

В отличие от типов инцидента (редактируемая БД-таблица incident_types), подтипы
заданы жёстко в коде и есть ТОЛЬКО у типа с кодом ``no_access`` («Отсутствует
доступ к МНО»). Тип-триггер — строковый код ``no_access`` (не зависит от БД-
справочника типов). Для остальных типов подтип не применяется (→ NULL).
"""

# Код типа инцидента → список его подтипов [{code, label}]. Значения фиксированы.
INCIDENT_SUBTYPES: dict[str, list[dict]] = {
    "no_access": [
        {"code": "blocked_by_car", "label": "Проезд заблокирован автомобилем"},
        {"code": "other_reason", "label": "Иная причина"},
    ],
}

# code подтипа → русская подпись (плоский индекс по всем типам) для быстрого резолва.
_LABEL_BY_CODE: dict[str, str] = {
    s["code"]: s["label"] for subs in INCIDENT_SUBTYPES.values() for s in subs
}


def subtypes_for(type_code: str) -> list[dict]:
    """Список подтипов [{code, label}] для типа инцидента ([] если подтипов нет)."""
    return list(INCIDENT_SUBTYPES.get(type_code, []))


def label_for(subtype_code) -> str:
    """Русская подпись подтипа по коду; "" для пустого/неизвестного кода."""
    if not subtype_code:
        return ""
    return _LABEL_BY_CODE.get(subtype_code, "")


def is_valid_subtype(type_code: str, subtype_code: str) -> bool:
    """True, если subtype_code принадлежит подтипам данного типа инцидента."""
    return any(s["code"] == subtype_code for s in INCIDENT_SUBTYPES.get(type_code, []))
