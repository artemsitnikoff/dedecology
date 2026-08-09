FROM python:3.12-slim

WORKDIR /app

# Никакого build-тулинга: httpx/pydantic/aiofiles поставляются колёсами. БЕЗ maxapi
# и python-telegram-bot — сырой Telegram Bot API поверх httpx.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Long-polling воркер — только исходящие соединения, без входящего порта / вебхука.
CMD ["python", "-m", "telegrambot.main"]
