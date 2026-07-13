"""Сервис технических ошибок мобильного приложения.

Централизованный приём/журнал: генерит уникальный код, пишет строку в БД, фиксирует
событие в лог-систему (logging → storage/logs) и шлёт письмо в техподдержку через
настроенный SMTP. Сбой/ненастроенность почты НЕ роняют запрос — ошибка всё равно
регистрируется, а email_error честно хранит причину недоставки. flush тут, commit — в роутере.
"""

import json
import logging
import math
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.errors import NotFoundError
from ..models import ErrorReport
from ..schemas.base import Paginated
from ..schemas.error_report import ErrorReportCreate, ErrorReportItem
from ..services import smtp as smtp_service

logger = logging.getLogger(__name__)

# Потолок сериализации тех.данных в теле письма — чтобы гигантский stacktrace/дамп
# не раздул письмо (в БД technical хранится целиком).
_TECH_EMAIL_LIMIT = 4000


def _gen_code() -> str:
    """Уникальный код ошибки: "ERR-" + 8 hex UPPER из uuid4 (напр. "ERR-A1B2C3D4")."""
    return "ERR-" + uuid.uuid4().hex[:8].upper()


async def _code_exists(session: AsyncSession, code: str) -> bool:
    """Есть ли уже строка с таким кодом (страховка от коллизии)."""
    result = await session.execute(
        select(ErrorReport.id).where(ErrorReport.code == code).limit(1)
    )
    return result.scalar_one_or_none() is not None


def _build_email(error: ErrorReport) -> tuple[str, str, str]:
    """(subject, body_text, body_html) человекочитаемого письма в техподдержку."""
    subject = f"ЭкоПульс · Ошибка {error.code} · {error.error_type}"

    tech_str = ""
    if error.technical:
        try:
            tech_str = json.dumps(error.technical, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            tech_str = str(error.technical)
        if len(tech_str) > _TECH_EMAIL_LIMIT:
            tech_str = tech_str[:_TECH_EMAIL_LIMIT] + "\n… (обрезано)"

    occurred = error.occurred_at.isoformat() if error.occurred_at else "—"

    lines = [
        "Зарегистрирована техническая ошибка мобильного приложения «ЭкоПульс».",
        "",
        f"Код ошибки: {error.code}",
        f"Тип: {error.error_type}",
        f"Описание: {error.message or '—'}",
        f"Версия приложения: {error.app_version or '—'}",
        f"Платформа: {error.platform or '—'}",
        f"Действие пользователя: {error.user_action or '—'}",
        f"Email волонтёра: {error.volunteer_email or '—'}",
        f"Время сбоя (клиент): {occurred}",
        "",
        "Технические данные:",
        tech_str or "—",
    ]
    body_text = "\n".join(lines)

    def _esc(v: object) -> str:
        return (
            str(v)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    body_html = (
        f"<p style=\"margin:0 0 12px;\">Зарегистрирована техническая ошибка "
        f"мобильного приложения <strong>«ЭкоПульс»</strong>.</p>"
        f"<table style=\"border-collapse:collapse;font-size:14px;\">"
        f"<tr><td style=\"padding:2px 8px;color:#666;\">Код ошибки</td>"
        f"<td style=\"padding:2px 8px;\"><strong>{_esc(error.code)}</strong></td></tr>"
        f"<tr><td style=\"padding:2px 8px;color:#666;\">Тип</td>"
        f"<td style=\"padding:2px 8px;\">{_esc(error.error_type)}</td></tr>"
        f"<tr><td style=\"padding:2px 8px;color:#666;\">Описание</td>"
        f"<td style=\"padding:2px 8px;\">{_esc(error.message or '—')}</td></tr>"
        f"<tr><td style=\"padding:2px 8px;color:#666;\">Версия приложения</td>"
        f"<td style=\"padding:2px 8px;\">{_esc(error.app_version or '—')}</td></tr>"
        f"<tr><td style=\"padding:2px 8px;color:#666;\">Платформа</td>"
        f"<td style=\"padding:2px 8px;\">{_esc(error.platform or '—')}</td></tr>"
        f"<tr><td style=\"padding:2px 8px;color:#666;\">Действие пользователя</td>"
        f"<td style=\"padding:2px 8px;\">{_esc(error.user_action or '—')}</td></tr>"
        f"<tr><td style=\"padding:2px 8px;color:#666;\">Email волонтёра</td>"
        f"<td style=\"padding:2px 8px;\">{_esc(error.volunteer_email or '—')}</td></tr>"
        f"<tr><td style=\"padding:2px 8px;color:#666;\">Время сбоя (клиент)</td>"
        f"<td style=\"padding:2px 8px;\">{_esc(occurred)}</td></tr>"
        f"</table>"
        f"<p style=\"margin:12px 0 4px;color:#666;\">Технические данные:</p>"
        f"<pre style=\"background:#f5f5f5;padding:8px;border-radius:6px;"
        f"font-size:12px;white-space:pre-wrap;word-break:break-word;\">"
        f"{_esc(tech_str) or '—'}</pre>"
    )
    return subject, body_text, body_html


async def create_error_report(
    session: AsyncSession, data: ErrorReportCreate
) -> ErrorReport:
    """Регистрирует техническую ошибку: уникальный код → строка → лог → письмо в поддержку.

    Письмо шлётся ПОСЛЕ flush. Любой сбой отправки (SMTP не настроен/недоступен) не
    роняет запрос: emailed=False, email_error=str(exc). flush; commit — в роутере.
    """
    # Уникальный код (перегенерируем при коллизии — практически невероятной).
    code = _gen_code()
    for _ in range(5):
        if not await _code_exists(session, code):
            break
        code = _gen_code()

    error = ErrorReport(
        code=code,
        error_type=data.error_type,
        message=data.message,
        app_version=data.app_version,
        user_action=data.user_action,
        platform=data.platform,
        technical=data.technical or {},
        occurred_at=data.occurred_at,
        volunteer_email=data.volunteer_email,
        emailed=False,
    )
    session.add(error)
    await session.flush()

    # Централизованная лог-система: фиксируем событие (logging → storage/logs).
    logger.error(
        "error_report registered code=%s type=%s app=%s action=%s",
        code,
        data.error_type,
        data.app_version,
        data.user_action,
    )

    # Письмо в техподдержку — best-effort, честно фиксируем исход.
    subject, body_text, body_html = _build_email(error)
    try:
        await smtp_service.send_email(
            session,
            to=settings.SUPPORT_EMAIL,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
        error.emailed = True
        error.email_error = None
    except Exception as exc:  # SMTP не настроен / сбой отправки
        error.emailed = False
        error.email_error = getattr(exc, "message", None) or str(exc)
        logger.warning(
            "error_report %s: письмо в поддержку не отправлено: %s",
            code,
            error.email_error,
        )

    await session.flush()
    return error


async def list_error_reports(
    session: AsyncSession, *, page: int = 1, page_size: int = 50
) -> Paginated[ErrorReportItem]:
    """Журнал ошибок — новейшие первыми (created_at desc, id desc)."""
    total = (
        await session.execute(select(func.count(ErrorReport.id)))
    ).scalar_one()

    result = await session.execute(
        select(ErrorReport)
        .order_by(ErrorReport.created_at.desc(), ErrorReport.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.scalars().all()
    items = [ErrorReportItem.model_validate(r) for r in rows]
    pages = math.ceil(total / page_size) if total > 0 else 0
    return Paginated[ErrorReportItem](
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


async def get_error_report(session: AsyncSession, report_id) -> ErrorReport:
    """Одна ошибка по id; нет → NotFoundError."""
    error = await session.get(ErrorReport, report_id)
    if error is None:
        raise NotFoundError("Обращение об ошибке")
    return error
