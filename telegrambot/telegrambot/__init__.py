"""ЭкоПульс Telegram messenger long-polling bot.

Outbound-only worker: long-polls the Telegram Bot API (getUpdates) for incoming
messages and forwards each report (photo + address/coords) to the ЭкоПульс
backend intake API, which creates an incident with source='telegram'. No inbound
port / webhook is required.

Зеркало сервиса maxbot/, но на СЫРОМ Telegram Bot API поверх httpx — БЕЗ
python-telegram-bot и без maxapi. Чистая логика (session.py, intake_client.py)
переносится почти дословно; вся Telegram-специфика — в tgapi.py + bot.py.
"""

__version__ = "0.1.0"
