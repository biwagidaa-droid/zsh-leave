"""Scoped Bradford reporting using the documented calendar-day policy."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db.models import F, Q, QuerySet

from zsh_core import reports as report_rules
from zsh_core import settings_schema

from .models import EmployeeProfile, LeaveRequest, LeaveType, SystemSetting

POLICY_VERSION = "calendar-days-v1"
MAX_WINDOW_DAYS = 366
DEFAULT_WINDOW_DAYS = 365
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 200
COUNTED_STATUSES = ("APPROVED", "WITHDRAWAL_PENDING")


class BradfordReportError(ValueError):
    def __init__(self, code: str, message_fa: str, status: int = 409):
        self.code = code
        self.message_fa = message_fa
        self.status = status
        super().__init__(message_fa)


def report_period(params, today: dt.date) -> tuple[dt.date, dt.date]:
    from_value, to_value = params.get("from"), params.get("to")
    if from_value is None and to_value is None:
        return today - dt.timedelta(days=DEFAULT_WINDOW_DAYS - 1), today
    try:
        if from_value is None or to_value is None:
            raise ValueError
        start = dt.date.fromisoformat(from_value)
        end = dt.date.fromisoformat(to_value)
        if start > end or end > today or (end - start).days + 1 > MAX_WINDOW_DAYS:
            raise ValueError
    except (TypeError, ValueError):
        raise BradfordReportError(
            "invalid_range",
            "بازه گزارش باید معتبر، غیرآینده و حداکثر ۳۶۶ روز باشد",
            400,
        )
    return start, end


def _configured_policy() -> tuple[dict, frozenset[str]]:
    stored = {item.key: item.value for item in SystemSetting.objects.all()}
    if "bradford.enabled" not in stored or "bradford.include_types" not in stored:
        raise BradfordReportError(
            "bradford_policy_not_configured",
            "سیاست Bradford هنوز به‌طور صریح پیکربندی و فعال نشده است",
        )
    if stored["bradford.enabled"] is not True:
        raise BradfordReportError(
            "bradford_disabled",
            "تحلیل Bradford در تنظیمات سازمان غیرفعال است",
        )
    try:
        values = settings_schema.resolve(stored)
    except settings_schema.SettingError as exc:
        raise BradfordReportError("invalid_bradford_configuration", str(exc))

    if values["bradford.include_hourly"]:
        raise BradfordReportError(
            "unsupported_bradford_configuration",
            "محاسبه مرخصی ساعتی تا زمان ثبت جزئیات کامل آن در مدل داده پشتیبانی نمی‌شود",
        )

    keys = {
        key.strip()
        for key in values["bradford.include_types"].split(",")
        if key.strip()
    }
    if not keys:
        raise BradfordReportError(
            "invalid_bradford_configuration",
            "حداقل یک نوع مرخصی مشمول Bradford باید مشخص شود",
        )
    configured_types = dict(
        LeaveType.objects.filter(key__in=keys).values_list("key", "confidential"),
    )
    if keys - configured_types.keys():
        raise BradfordReportError(
            "invalid_bradford_configuration",
            "یکی از انواع مرخصی تنظیم‌شده برای Bradford وجود ندارد",
        )
    eligible_keys = frozenset(
        key for key in keys if not configured_types[key]
    )
    if not eligible_keys:
        raise BradfordReportError(
            "invalid_bradford_configuration",
            "نوع مرخصی غیرمحرمانه‌ای برای محاسبه Bradford پیکربندی نشده است",
        )
    return values, eligible_keys


def calculate_bradford_report(
    *,
    employees: QuerySet[EmployeeProfile],
    start: dt.date,
    end: dt.date,
    offset: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
) -> dict:
    """Calculate complete scores for one explicitly paginated page of scoped employees."""
    values, eligible_type_keys = _configured_policy()
    population = employees.filter(
        is_employee=True,
        start_date__lte=end,
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=start)).distinct().order_by("pk")
    population_count = population.count()
    min_group_size = values["privacy.min_group_size"]

    if population_count == 0:
        return {
            "status": "empty",
            "series": [],
            "pagination": {"offset": offset, "limit": limit, "total": 0},
            "empty_state_reason": "no_employees_in_period",
            "warnings": [],
        }
    if population_count < min_group_size:
        return {
            "status": "suppressed",
            "series": [],
            "pagination": {"offset": offset, "limit": limit, "total": population_count},
            "empty_state_reason": "minimum_group_size",
            "warnings": [],
        }
    page = list(population[offset:offset + limit].values(
        "pk", "personnel_code", "user__first_name", "user__last_name", "user__username",
    ))
    if not page:
        return {
            "status": "provisional",
            "series": [],
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": population_count,
                "hasMore": False,
            },
            "empty_state_reason": "page_out_of_range",
            "warnings": [],
        }

    page_employee_ids = [employee["pk"] for employee in page]
    intervals: dict[int, list[tuple[dt.date, dt.date]]] = {}
    requests = LeaveRequest.objects.filter(
        employee_id__in=page_employee_ids,
        leave_type__key__in=eligible_type_keys,
        leave_type__confidential=False,
        status__in=COUNTED_STATUSES,
        start_date__lte=end,
        end_date__gte=start,
    ).filter(
        end_date__gte=F("employee__start_date"),
    ).filter(
        Q(employee__end_date__isnull=True)
        | Q(start_date__lte=F("employee__end_date")),
    ).values_list(
        "employee_id", "employee__start_date", "employee__end_date",
        "start_date", "end_date", "working_days",
    )
    for employee_id, employed_from, employed_to, leave_from, leave_to, working_days in requests.iterator(
        chunk_size=2000,
    ):
        days = Decimal(working_days)
        if days != days.to_integral_value():
            raise BradfordReportError(
                "incomplete_partial_day_data",
                "به‌دلیل وجود مرخصی جزئی، جزئیات روزانه کافی برای محاسبه دقیق Bradford موجود نیست",
            )
        clipped_start = max(start, employed_from, leave_from)
        clipped_end = min(end, employed_to or end, leave_to)
        if clipped_start <= clipped_end:
            intervals.setdefault(employee_id, []).append((clipped_start, clipped_end))

    score_by_employee = {
        employee_id: report_rules.bradford_factor(spans, start, end)
        for employee_id, spans in intervals.items()
    }

    series = []
    for employee in page:
        score = score_by_employee.get(employee["pk"], {
            "spells": 0, "days": 0, "score": 0,
        })
        display_name = " ".join(
            part for part in (employee["user__first_name"], employee["user__last_name"]) if part
        ).strip() or employee["user__username"]
        series.append({
            "employeeId": employee["pk"],
            "personnelCode": employee["personnel_code"],
            "displayName": display_name,
            "spells": score["spells"],
            "days": score["days"],
            "score": score["score"],
        })

    has_absences = bool(score_by_employee)
    return {
        "status": "provisional",
        "series": series,
        "pagination": {
            "offset": offset,
            "limit": limit,
            "total": population_count,
            "hasMore": offset + len(series) < population_count,
        },
        "empty_state_reason": None if has_absences else "no_eligible_absences",
        "warnings": [
            {
                "code": "policy_requires_business_approval",
                "message_fa": "قاعده فعلی بر مبنای تاریخ تقویمی است و تا تصویب رسمی سیاست، موقت محسوب می‌شود.",
            },
            {
                "code": "confidential_types_excluded",
                "message_fa": "انواع مرخصی محرمانه پیش از محاسبه و خروجی حذف می‌شوند.",
            },
        ],
    }
