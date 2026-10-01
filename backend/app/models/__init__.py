from .base import Base, TimestampMixin, CreatedAtMixin
from .user import User
from .incident import Incident
from .audit import AuditLog
from .region import Region
from .mno import Mno
from .incident_type import IncidentType
from .blocked_domain import BlockedEmailDomain
from .volunteer import Volunteer
from .smtp import SmtpSettings
from .report import Report
from .quote import Quote
from .error_report import ErrorReport

# УТКО-совместимое API (ядро приёма данных посещения МНО) — отдельный пакет app/utko,
# но модели наследуют общий Base, поэтому регистрируем их в общей metadata здесь
# (create_all/alembic autogenerate видят таблицы utko_* вместе с доменными).
from ..utko.models import (
    UtkoTruckVisitEvent,
    UtkoTruckVisitConfirm,
    UtkoVideoEvent,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "CreatedAtMixin",
    "User",
    "Incident",
    "AuditLog",
    "Region",
    "Mno",
    "IncidentType",
    "BlockedEmailDomain",
    "Volunteer",
    "SmtpSettings",
    "Report",
    "Quote",
    "ErrorReport",
    "UtkoTruckVisitEvent",
    "UtkoTruckVisitConfirm",
    "UtkoVideoEvent",
]
