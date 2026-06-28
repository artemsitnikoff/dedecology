"""AI-разбор свободного текста обращения из Макс-бота через claude CLI.

Пользователь Макса присылает адрес площадки ТКО одной свободной строкой
(«Нижегородская область, г. Нижний Новгород, … улица Сергея Есенина, 38
(Радар №116495, 26 июня 2026, 10:28)»). claude CLI извлекает из неё
структурированные поля (регион/город/улица/координаты/время), которые затем
стандартизируются и геокодируются через DaData (см. intake.create_incident_from_max).

Используется ТОЛЬКО для приёма из Макс-бота (/intake/max). Любой сбой CLI или
разбора JSON → None: вызывающий код деградирует на DaData Clean / эвристику.
Функция никогда не бросает исключений.
"""

import json
import logging
import re

from ..config import settings
from . import parse_log
from .claude_cli import claude_cli_complete

logger = logging.getLogger(__name__)

# Ожидаемые ключи структурированного разбора (порядок не важен).
_KEYS = ("region", "city", "street", "coords", "time", "comment")

# Промпт собираем конкатенацией (в литерале JSON есть фигурные скобки —
# f-string/format здесь только мешали бы). Текст обращения вставляется между
# маркерами <<< >>>, чтобы модель не путала инструкцию с данными.
#
# Текст «грязный»: нейронка Макс-бота кладёт в одну строку ФИО заявителя, дату,
# время и описание проблемы вперемешку с адресом — поэтому промпт ЯВНО велит
# вынести лишнее из адреса в comment и добавляет один few-shot пример (регион/
# город разделены, прочее собрано в comment).
_PROMPT_PREFIX = (
    "Извлеки адрес площадки ТКО из свободного текста обращения. Верни СТРОГО один "
    "JSON-объект без пояснений и без markdown: "
    '{"region": "", "city": "", "street": "", "coords": "", "time": "", "comment": ""}. '
    "В тексте ЧАСТО есть НЕ-адресные данные — ФИО заявителя, «Радар №…», дата, "
    "описание проблемы (напр. «Баки раздельного сбора отсутствуют»), заметки. "
    "В поля адреса их НЕ клади — собери в comment. Правила полей: "
    "region — субъект РФ (край / область / республика / город федерального "
    "значения), напр. «Краснодарский край», «Самарская область», «Москва». "
    "city — город или населённый пункт БЕЗ слова «край»/«область» "
    "(напр. «Сочи», «Нижний Новгород»); НЕ дублируй сюда регион. "
    "street — ТОЛЬКО улица и дом, БЕЗ «Радар №…», без описаний, ориентиров и пояснений "
    "(адрес должен поддаваться геокодированию; «Радар №…» — это НЕ часть адреса). "
    "coords — \"широта, долгота\" ТОЛЬКО если в тексте явно есть числа координат, "
    "иначе пусто. time — время фотофиксации в формате ЧЧ:ММ если есть, иначе пусто. "
    "comment — вся ПРОЧАЯ информация из текста, НЕ относящаяся к адресу: «Радар №…», "
    "ФИО заявителя, описание проблемы (напр. «Баки раздельного сбора отсутствуют»), "
    "заметки. Собери в одну строку через «; »; если ничего такого нет — пусто. "
    "Пример. Вход: «Бахтин Владимир Вадимович Краснодарский край Г.Сочи "
    "27.06.2026 19:06 Олимпийская улица 38/9 (Радар №116434) Баки раздельного сбора отсутствуют». "
    'Выход: {"region": "Краснодарский край", "city": "Сочи", '
    '"street": "Олимпийская улица, 38/9", "coords": "", "time": "19:06", '
    '"comment": "Бахтин Владимир Вадимович; Радар №116434; Баки раздельного сбора отсутствуют"}. '
    "(Заметь: «Радар №116434», ФИО, дата и описание в адрес НЕ попали — они в comment.) "
    "Текст обращения: <<<"
)
_PROMPT_SUFFIX = ">>>"


def _as_str(value) -> str:
    """Любое значение из JSON → стрипнутая строка ('' для None)."""
    if value is None:
        return ""
    return str(value).strip()


def _extract_json(raw: str) -> dict | None:
    """Извлекает первый JSON-объект из ответа CLI. None при любой неудаче.

    Снимает markdown-ограждения (```json … ```), отбрасывает поясняющую прозу
    вокруг и парсит подстроку от первого `{` до последнего `}`.
    """
    s = (raw or "").strip()
    if not s:
        return None

    # Снять markdown-ограждения, если модель всё же обернула ответ.
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9]*\s*", "", s)
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()

    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        data = json.loads(s[start : end + 1])
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


async def ai_parse_incident(text: str) -> dict | None:
    """Структурированный разбор свободного текста обращения через claude CLI.

    Возвращает dict с 6 строковыми ключами (region/city/street/coords/time/comment;
    отсутствующие → ""). None, если текст пуст, CLI недоступен или ответ не
    содержит валидного JSON-объекта. Никогда не бросает исключений.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    model = settings.CLAUDE_PARSE_MODEL
    prompt = _PROMPT_PREFIX + cleaned + _PROMPT_SUFFIX
    try:
        raw = await claude_cli_complete(
            prompt=prompt,
            model=model,
            timeout=settings.CLAUDE_QUOTE_TIMEOUT,
        )
    except Exception as e:  # noqa: BLE001 — CLI не должен ронять приём
        logger.warning("[incident_parse] сбой claude CLI: %s: %s", type(e).__name__, e)
        parse_log.log_ai(cleaned, model, prompt, f"(ошибка CLI: {type(e).__name__})", None)
        return None

    if not raw:
        parse_log.log_ai(cleaned, model, prompt, None, None)
        return None

    data = _extract_json(raw)
    if data is None:
        logger.warning("[incident_parse] не удалось извлечь JSON из ответа CLI")
        parse_log.log_ai(cleaned, model, prompt, raw, None)
        return None

    result = {key: _as_str(data.get(key)) for key in _KEYS}
    parse_log.log_ai(cleaned, model, prompt, raw, result)
    return result
