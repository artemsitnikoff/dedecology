"""Общая настройка тестов telegrambot.

* Кладём корень сервиса в sys.path, чтобы `import telegrambot.*` работал при запуске
  из любой директории интерпретатором без установки пакета.
* Проставляем безопасные фиктивные значения окружения ДО импорта config/bot — иначе
  `Settings()` (требует TELEGRAM_BOT_TOKEN) уронил бы импорт модулей, читающих settings.
  tgapi и session от settings не зависят и тестируются без этого, но подстраховка не мешает.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token:for-unit-tests")
os.environ.setdefault("INTAKE_TOKEN", "test-intake-token")
