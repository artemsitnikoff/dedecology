"""Фоновый цикл GROUP-NOTIFICATION для ЭкоПульс.

Периодически опрашивает backend на наличие обращений, ещё не отправленных в
групповой чат Макса (notified_at IS NULL), и постит каждое в чат, где бот —
админ: текст «зарегистрировано в ЭкоПульс» + детали + фото + «Спасибо!» + цитата.

Дизайн устойчивости:
* нет MAX_GROUP_CHAT_ID → цикл логирует один раз и выходит (фича выключена);
* внешний try/except оборачивает каждую итерацию — цикл не умирает никогда;
* per-incident try/except: сбойное обращение НЕ помечается отправленным и
  переотправится на следующей итерации;
* mark_notified вызывается только для реально запостенных обращений.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from maxapi.types import InputMediaBuffer

from .config import settings
from .intake_client import download_photo, fetch_pending, mark_notified

logger = logging.getLogger("dedecology.maxbot")

# Максимум фото на одно обращение в групповом сообщении.
_MAX_PHOTOS = 3


def _format_photo_time(photo_time: str | None) -> str | None:
    """ISO-строку времени фотофиксации → «ДД.ММ.ГГГГ ЧЧ:ММ»; None при пустом/кривом."""
    if not photo_time:
        return None
    try:
        dt = datetime.fromisoformat(photo_time)
    except ValueError:
        logger.warning("bad photo_time format: %r", photo_time)
        return None
    return dt.strftime("%d.%m.%Y %H:%M")


def _build_message(incident: dict) -> str:
    """Собрать текст уведомления для группового чата из полей обращения."""
    source_raw = (incident.get("source") or "").strip().lower()
    is_max = source_raw.startswith("max") or source_raw == "макс"
    source_label = "Макс" if is_max else "Форма"

    lines: list[str] = ["🟢 Новое обращение — ЭкоПульс", f"Источник: {source_label}"]

    fio = (incident.get("fio") or "").strip()
    if fio:
        lines.append(f"ФИО: {fio}")

    address_parts = [
        (incident.get("region") or "").strip(),
        (incident.get("city") or "").strip(),
        (incident.get("street") or "").strip(),
    ]
    address = ", ".join(part for part in address_parts if part)
    if address:
        lines.append(f"Адрес: {address}")

    coords = (incident.get("coords") or "").strip()
    if coords:
        lines.append(f"Координаты: {coords}")

    photo_time = _format_photo_time(incident.get("photo_time"))
    if photo_time:
        lines.append(f"Время фотофиксации: {photo_time}")

    # Ссылка на сообщение = готовый https-URL из msg_url КАК ЕСТЬ. Показываем только если
    # он непустой и начинается с http; битые ссылки не выводим (поле msg для ссылки не используем).
    url = (incident.get("msg_url") or "").strip()
    if url.startswith("http"):
        lines.append(f"Сообщение: {url}")

    lines.append("")
    lines.append("Спасибо!")

    quote = (incident.get("quote") or "").strip()
    if quote:
        lines.append(quote)

    return "\n".join(lines)


async def _download_photos(incident: dict) -> list[bytes]:
    """Скачать до _MAX_PHOTOS фото обращения; сбойные/большие — пропустить."""
    urls = incident.get("photo_urls") or []
    if not isinstance(urls, list):
        return []
    photos: list[bytes] = []
    for url_path in urls[:_MAX_PHOTOS]:
        data = await download_photo(url_path)
        if data is not None:
            photos.append(data)
    return photos


async def _notify_one(bot, incident: dict) -> None:
    """Запостить одно обращение в групповой чат. Бросает при сбое отправки."""
    text = _build_message(incident)
    photos = await _download_photos(incident)
    attachments = [
        InputMediaBuffer(buffer=photo, filename=f"{i}.jpg")
        for i, photo in enumerate(photos)
    ]
    await bot.send_message(
        chat_id=settings.MAX_GROUP_CHAT_ID,
        text=text,
        attachments=attachments or None,
    )


async def notify_loop(bot) -> None:
    """Фоновый цикл: опрашивает backend и постит новые обращения в групповой чат."""
    if settings.MAX_GROUP_CHAT_ID is None:
        logger.info("group notifications disabled — MAX_GROUP_CHAT_ID is not set")
        return

    logger.info(
        "group notification loop started — chat_id=%s interval=%ss",
        settings.MAX_GROUP_CHAT_ID,
        settings.NOTIFY_INTERVAL,
    )

    while True:
        await asyncio.sleep(settings.NOTIFY_INTERVAL)
        try:
            incidents = await fetch_pending()
            if not incidents:
                continue

            succeeded: list[str] = []
            for incident in incidents:
                incident_id = incident.get("id")
                try:
                    await _notify_one(bot, incident)
                except Exception:  # noqa: BLE001 — один сбой не должен ронять цикл
                    logger.exception(
                        "failed to notify incident id=%s — will retry next loop",
                        incident_id,
                    )
                    continue
                if incident_id:
                    succeeded.append(str(incident_id))

            if succeeded:
                try:
                    await mark_notified(succeeded)
                except Exception:  # noqa: BLE001 — переотправятся на следующей итерации
                    logger.exception(
                        "mark_notified failed for %d incident(s) — will retry next loop",
                        len(succeeded),
                    )
        except asyncio.CancelledError:
            logger.info("notify loop cancelled — shutting down")
            raise
        except Exception:  # noqa: BLE001 — цикл не умирает никогда
            logger.exception("notify loop iteration failed — continuing")
