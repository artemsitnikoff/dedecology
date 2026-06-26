FROM python:3.12-slim

WORKDIR /app

# No build toolchain needed: maxapi/httpx/pydantic ship wheels.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Long-polling worker — outbound only, no inbound port / webhook.
CMD ["python", "-m", "maxbot.main"]
