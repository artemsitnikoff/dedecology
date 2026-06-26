"""Обёртка над claude CLI (`claude --print`) для генерации короткого текста.

Stateless prompt→answer. Используется для мотивирующей цитаты о природе на
успешном приёме обращения. Это ЧИСТАЯ генерация текста — ВСЕ инструменты
выключены (--disallowed-tools), чтобы CLI не выполнял shell/файлы по промпту.

Авторизация — долгоживущий OAuth-токен (CLAUDE_TOKEN_FILE → CLAUDE_CODE_OAUTH_TOKEN).
Любой сбой (CLI не установлен, токен пуст/невалиден, таймаут, пустой ответ) →
возвращаем None. Вызывающий код обязан иметь фолбэк, НЕ блокироваться.
"""

import asyncio
import json
import logging
import os

from ..config import settings

logger = logging.getLogger(__name__)


def resolve_claude_token() -> str:
    """Текущий access_token для claude CLI.

    Приоритет — токен-файл (CLAUDE_TOKEN_FILE, JSON {access_token}); читаем
    только access_token (НЕ рефрешим). Фолбэк — CLAUDE_CODE_OAUTH_TOKEN из env.
    Пусто → генерация не выполняется.
    """
    path = settings.CLAUDE_TOKEN_FILE
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            token = (data.get("access_token") or "").strip()
            if token:
                return token
            logger.warning("[claude_cli] в %s нет access_token", path)
        except (OSError, ValueError) as e:
            logger.warning("[claude_cli] не прочитать токен-файл %s: %s", path, e)
    return settings.CLAUDE_CODE_OAUTH_TOKEN.strip()


# Чистая генерация текста — запрещаем ВСЕ инструменты (без --allowed-tools).
_DISALLOWED_TOOLS = "Bash,Edit,Write,Read,Glob,Grep,WebSearch,WebFetch,NotebookEdit,Task"


async def claude_cli_complete(
    *,
    prompt: str,
    model: str | None = None,
    timeout: int | None = None,
    system: str | None = None,
) -> str | None:
    """Выполнить prompt через claude CLI. Возвращает текст ответа или None при сбое.

    Никогда не бросает исключений — при любой проблеме логирует warning и
    возвращает None (вызывающий код деградирует на фолбэк).
    """
    token = resolve_claude_token()
    if not token:
        logger.info("[claude_cli] токен не найден (ни файл, ни env) — генерация пропущена")
        return None

    chosen_model = model or settings.CLAUDE_QUOTE_MODEL
    timeout = timeout or settings.CLAUDE_QUOTE_TIMEOUT

    args = [
        settings.CLAUDE_CLI_PATH,
        "--print",
        "--output-format", "text",
        "--disallowed-tools", _DISALLOWED_TOOLS,
    ]
    if chosen_model:
        args.extend(["--model", chosen_model])
    if system:
        args.extend(["--append-system-prompt", system])

    # env с токеном; CLAUDECODE убираем, чтобы CLI не считал себя вложенным.
    # Least-privilege: НЕ отдаём секреты приложения дочернему процессу.
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    for _k in list(env):
        _ku = _k.upper()
        if ("SECRET" in _ku or "PASSWORD" in _ku or _ku.endswith("_KEY")
                or _ku.endswith("_TOKEN") or _ku.endswith("_HASH")
                or _ku in ("DATABASE_URL", "JWT_SECRET")):
            env.pop(_k, None)
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token  # ставим ПОСЛЕ чистки

    logger.info("[claude_cli] запуск генерации (model=%s, timeout=%ss)", chosen_model or "default", timeout)

    try:
        # cwd=/tmp — чтобы CLI не подхватил CLAUDE.md проекта как контекст
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd="/tmp",
        )
    except (FileNotFoundError, OSError) as e:
        logger.warning("[claude_cli] CLI не запустился (%s): %s", type(e).__name__, e)
        return None

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode()), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        logger.warning("[claude_cli] таймаут генерации за %sс", timeout)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("[claude_cli] сбой связи с CLI: %s", e)
        return None

    if proc.returncode != 0:
        err = (stderr.decode(errors="replace").strip() or stdout.decode(errors="replace").strip())[:300]
        logger.warning("[claude_cli] код %s: %s", proc.returncode, err)
        return None

    result = stdout.decode(errors="replace").strip()
    if not result:
        logger.warning("[claude_cli] пустой ответ")
        return None
    return result
