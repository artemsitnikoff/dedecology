"""maxapi 0.9.4 compatibility layer for the ДедЭколог maxbot.

Single source of truth for anything maxapi-version-specific. `apply_patches()`
is the only side-effecting call; it is idempotent and version-guarded.

What this maxbot actually needs from maxapi 0.9.4 — and where it is handled:

1. Authorization header (the 401 fix).
   maxapi 0.9.4 only sends the token via the `?access_token=…` query string;
   the MAX Bot API now rejects that with 401 and wants
   `Authorization: <token>` as a header. This is NOT a monkey-patch — it is
   constructor config. `maxbot.bot.create_bot()` passes
   `DefaultConnectionProperties(headers={"Authorization": token})`, and maxapi
   forwards those kwargs straight into `aiohttp.ClientSession(...)`
   (see maxapi/connection/base.py: `ClientSession(..., **default_connection.kwargs)`),
   so the header is attached to every request. Verified against 0.9.4 source.

2. Handler kwarg injection (Dispatcher.call_handler).
   maxapi 0.9.4 injects handler kwargs by `func_event.__annotations__`, and the
   dispatcher only ever offers a `context` kwarg. Our handler is single-arg
   (`async def handler(event: MessageCreated)`), so the event is passed
   positionally and nothing extra is required — the `inspect.signature` patch
   the multi-arg ArkadyJarvisMAX bot needs is intentionally NOT applied here.
   `_patch_dispatcher_call_handler()` is kept (unused) so a future handler that
   takes extra un-annotated kwargs can enable it with a one-line change.

Bump maxapi → re-verify the two facts above and update _TESTED_VERSIONS.
"""

from __future__ import annotations

import inspect
import logging
from importlib.metadata import PackageNotFoundError, version as _pkg_version

logger = logging.getLogger("dedecology.maxbot")

# Versions these compat assumptions were actually verified against.
_TESTED_VERSIONS = {"0.9.4"}

_applied = False


def _check_version() -> None:
    try:
        installed = _pkg_version("maxapi")
    except PackageNotFoundError:
        logger.warning("maxapi package metadata not found — skipping version check")
        return
    if installed not in _TESTED_VERSIONS:
        logger.warning(
            "maxapi==%s is installed but maxbot was verified only on %s. "
            "Re-check the Authorization-header fix and handler dispatch before prod.",
            installed,
            sorted(_TESTED_VERSIONS),
        )


def _patch_dispatcher_call_handler() -> None:
    """Inject handler kwargs by inspect.signature instead of __annotations__.

    NOT applied by default — our single-`event` handler does not need it. Kept
    here so a future multi-arg handler can opt in by calling this from
    `apply_patches()`.
    """
    from maxapi.dispatcher import Dispatcher as _Dispatcher

    async def _patched(self, handler, event_object, data):
        sig = inspect.signature(handler.func_event)
        param_names = set(sig.parameters.keys())
        kwargs = {k: v for k, v in data.items() if k in param_names}
        await handler.func_event(event_object, **kwargs)

    _Dispatcher.call_handler = _patched
    logger.info("maxapi compat: Dispatcher.call_handler signature-injection patch applied")


def apply_patches() -> None:
    """Run the version guard. Idempotent — safe to call more than once.

    Currently applies no runtime monkey-patches: the Authorization fix is
    constructor config in create_bot(), and the default handler dispatch works
    for a single-`event` handler (see module docstring).
    """
    global _applied
    if _applied:
        return
    _check_version()
    _applied = True
    logger.info("maxapi 0.9.4 compat layer initialised (no runtime patches required)")
