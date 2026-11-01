from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Iterable, Mapping

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import EmployeeProfile

INELIGIBLE_ACCOUNT_STATUSES = {
    EmployeeProfile.ACCOUNT_SUSPENDED,
    EmployeeProfile.ACCOUNT_OFFBOARDED,
}
STATUS_AUDIT_ACTIONS = {
    "account.suspended": EmployeeProfile.ACCOUNT_SUSPENDED,
    "account.offboarded": EmployeeProfile.ACCOUNT_OFFBOARDED,
    "activation.succeeded": EmployeeProfile.ACCOUNT_ACTIVATED,
}


def organization_timezone() -> dt.tzinfo:
    return timezone.get_default_timezone()


def organization_localdate(value: dt.datetime | None = None) -> dt.date:
    """Return a date in the configured organization timezone, not the host timezone."""
    return timezone.localdate(value or timezone.now(), organization_timezone())


def employment_filter(on_date: dt.date | None = None) -> Q:
    """Build the ORM equivalent of the authoritative point-in-time employment rule."""
    effective_date = on_date or organization_localdate()
    if isinstance(effective_date, dt.datetime):
        raise TypeError("Employment dates must be date values, not datetimes.")
    eligible = (
        Q(is_employee=True, start_date__lte=effective_date)
        & (Q(end_date__isnull=True) | Q(end_date__gte=effective_date))
    )
    if effective_date >= organization_localdate():
        eligible &= ~Q(account_status__in=INELIGIBLE_ACCOUNT_STATUSES)
    return eligible


def employees_employed_on(
    queryset: QuerySet[EmployeeProfile],
    on_date: dt.date | None = None,
) -> QuerySet[EmployeeProfile]:
    return queryset.filter(employment_filter(on_date))


def employment_status_history(
    employee_ids: Iterable[int],
    *,
    through_date: dt.date,
) -> dict[int, list[tuple[dt.date, str]]]:
    """Load audited suspension/offboarding transitions in one query for historical snapshots."""
    if isinstance(through_date, dt.datetime):
        raise TypeError("Employment dates must be date values, not datetimes.")

    ids = tuple(employee_ids)
    if not ids:
        return {}

    from .models import AuditEvent

    end_of_day = dt.datetime.combine(
        through_date + dt.timedelta(days=1),
        dt.time.min,
        tzinfo=organization_timezone(),
    )
    events = AuditEvent.objects.filter(
        entity="EmployeeProfile",
        entity_id__in=[str(employee_id) for employee_id in ids],
        action__in=STATUS_AUDIT_ACTIONS,
        created_at__lt=end_of_day,
    ).order_by("created_at", "pk").values_list("entity_id", "action", "created_at")
    history: dict[int, list[tuple[dt.date, str]]] = defaultdict(list)
    for employee_id, action, created_at in events:
        event_date = timezone.localtime(created_at, organization_timezone()).date()
        history[int(employee_id)].append((event_date, STATUS_AUDIT_ACTIONS[action]))
    return dict(history)


def is_employed_on(
    employee: EmployeeProfile | Mapping[str, object],
    on_date: dt.date | None = None,
    *,
    status_history: Iterable[tuple[dt.date, str]] | None = None,
) -> bool:
    """Whether an employee is eligible on a date; both employment-date boundaries are inclusive."""
    effective_date = on_date or organization_localdate()
    if isinstance(effective_date, dt.datetime):
        raise TypeError("Employment dates must be date values, not datetimes.")

    def value(field: str):
        return employee[field] if isinstance(employee, Mapping) else getattr(employee, field)

    start_date = value("start_date")
    end_date = value("end_date")
    if (
        not value("is_employee")
        or start_date > effective_date
        or (end_date is not None and end_date < effective_date)
    ):
        return False

    current_status = value("account_status")
    if effective_date >= organization_localdate():
        return current_status not in INELIGIBLE_ACCOUNT_STATUSES

    if status_history is not None:
        status_at_date = None
        for event_date, status in status_history:
            if event_date > effective_date:
                break
            status_at_date = status
        return status_at_date not in INELIGIBLE_ACCOUNT_STATUSES
    return True


def is_employed_throughout(
    employee: EmployeeProfile,
    start: dt.date,
    end: dt.date,
) -> bool:
    return start <= end and is_employed_on(employee, start) and is_employed_on(employee, end)
