"""Сервис отчётов — синхронная генерация Excel-выгрузок обращений с сохранением на диск.

Переиспользует incident_service (list_for_export / list_by_ids) и export.build_xlsx —
логика выборки/формирования .xlsx НЕ дублируется. Файл пишется на диск по пути
{STORAGE_DIR}/reports/{id}.xlsx, строка — в таблицу reports; скачивание отдаёт реально
сохранённый файл, отсутствие файла/строки → честный 404 (NotFoundError).
"""

import math
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.v1.incidents import _as_datetime
from ..config import settings
from ..core.errors import NotFoundError
from ..models import Report, User
from ..schemas.base import Paginated
from ..schemas.report import ReportCreateRequest, ReportListItem
from ..services import incident as incident_service
from ..services import incident_type as incident_type_service
from ..services.audit import audit
from ..services.utko_export import build_utko_xlsx


def _reports_dir() -> Path:
    """Каталог хранения файлов отчётов (создаётся при первом обращении)."""
    path = Path(settings.STORAGE_DIR) / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def create_incidents_report(
    session: AsyncSession,
    current_user: User,
    *,
    base_url: str,
    req: ReportCreateRequest,
) -> Report:
    """Синхронно формирует .xlsx по обращениям, пишет файл на диск + строку reports.

    ids непуст → выгрузка выбранных (list_by_ids); иначе — по фильтру (list_for_export).
    commit — в роутере.
    """
    if req.ids:
        rows = await incident_service.list_by_ids(session, req.ids)
    else:
        rows = await incident_service.list_for_export(
            session,
            search=req.search,
            source=req.source,
            status=req.status,
            date_from=_as_datetime(req.date_from),
            date_to=_as_datetime(req.date_to),
            region=req.region,
            sort=req.sort,
            order=req.order,
        )

    type_labels = await incident_type_service.labels_map(session)
    content = build_utko_xlsx(rows, base_url, type_labels)

    # Формирование отчёта = выгрузка: включённые в него обращения СРАЗУ переходят в
    # статус «Выгружен» (по требованию). Файл собран ВЫШЕ — в нём статусы на момент
    # выгрузки (снимок). Идемпотентно: уже выгруженные не трогаем и не считаем.
    exported_now = 0
    for inc in rows:
        if inc.status != "exported":
            inc.status = "exported"
            exported_now += 1
    if exported_now:
        await session.flush()

    now = datetime.now(timezone.utc)
    if req.ids:
        filename = f"Выгрузка_УТКО_{now:%Y-%m-%d_%H-%M}_выбранные.xlsx"
    else:
        filename = f"Выгрузка_УТКО_{now:%Y-%m-%d_%H-%M}.xlsx"

    report = Report(
        kind="incidents",
        filename=filename,
        created_by_id=current_user.id,
        created_by_fio=current_user.fio,
        row_count=len(rows),
        size_bytes=len(content),
    )
    session.add(report)
    await session.flush()  # получить report.id для имени файла на диске

    path = _reports_dir() / f"{report.id}.xlsx"
    path.write_bytes(content)

    await audit(
        session,
        action="report_created",
        entity_type="report",
        entity_id=report.id,
        after={
            "filename": report.filename,
            "row_count": report.row_count,
            "size_bytes": report.size_bytes,
        },
        actor_user_id=current_user.id,
    )
    # Отдельный аудит массового перевода в «Выгружен» (если что-то реально изменилось).
    if exported_now:
        await audit(
            session,
            action="incidents_marked_exported",
            entity_type="incident",
            entity_id=None,
            after={"count": exported_now, "report": report.filename},
            actor_user_id=current_user.id,
        )
    await session.flush()
    return report


async def list_reports(
    session: AsyncSession, *, page: int = 1, page_size: int = 50
) -> Paginated[ReportListItem]:
    """История отчётов — новейшие первыми (created_at desc, id desc)."""
    total = (
        await session.execute(select(func.count(Report.id)))
    ).scalar_one()

    result = await session.execute(
        select(Report)
        .order_by(Report.created_at.desc(), Report.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.scalars().all()
    items = [ReportListItem.model_validate(r) for r in rows]
    pages = math.ceil(total / page_size) if total > 0 else 0
    return Paginated[ReportListItem](
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


async def get_for_download(
    session: AsyncSession, report_id: UUID
) -> tuple[Path, str]:
    """(path, filename) для скачивания; нет строки/файла → NotFoundError (404)."""
    report = await session.get(Report, report_id)
    if report is None:
        raise NotFoundError("Отчёт")
    path = _reports_dir() / f"{report_id}.xlsx"
    if not path.exists():
        raise NotFoundError("Файл отчёта")
    return path, report.filename


async def delete_report(
    session: AsyncSession, report_id: UUID, current_user: User
) -> None:
    """Удаляет строку отчёта + файл на диске (missing_ok). commit — в роутере."""
    report = await session.get(Report, report_id)
    if report is None:
        raise NotFoundError("Отчёт")
    filename = report.filename
    await session.delete(report)
    (_reports_dir() / f"{report_id}.xlsx").unlink(missing_ok=True)
    await audit(
        session,
        action="report_deleted",
        entity_type="report",
        entity_id=report_id,
        after={"filename": filename},
        actor_user_id=current_user.id,
    )
    await session.flush()
