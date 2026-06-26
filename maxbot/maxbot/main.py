"""Entrypoint for the ДедЭколог MAX long-polling worker.

Outbound-only: connects out to the MAX Bot API, polls for updates and forwards
each message to the backend intake API. No inbound port / webhook is used.
"""

from __future__ import annotations

import asyncio
import logging

from maxapi import Dispatcher

# Init the maxapi compat layer before building the bot/dispatcher.
from .maxapi_compat import apply_patches as _apply_maxapi_patches

_apply_maxapi_patches()

from .bot import build_router, create_bot  # noqa: E402 — must follow patch init

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dedecology.maxbot")


async def main() -> None:
    bot = create_bot()
    dp = Dispatcher()
    dp.include_routers(build_router())

    # Any prior webhook subscription starves long-polling of events. Wipe it.
    try:
        await bot.delete_webhook()
    except Exception as exc:  # noqa: BLE001 — non-fatal; log and keep going
        logger.warning("delete_webhook failed: %s", exc)

    logger.info("MAX bot polling started — build 0.3.3 (CI auto-rebuild test)")
    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        logger.info("polling cancelled — shutting down")
        raise
    finally:
        await bot.close_session()
        logger.info("session closed, shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("interrupted by user — exiting")
