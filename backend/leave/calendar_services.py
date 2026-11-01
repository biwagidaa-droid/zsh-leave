from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, Q

from zsh_core import holidays as holiday_rules
from zsh_core import settings_schema
from zsh_core.policy import LeavePolicy
from .models import (
    AuditEvent,
    CalendarHoliday,
    CalendarHolidayHistory,
    Company,
    EmployeeProfile,
    LeavePolicyVersion,
    PublicHoliday,
    WorkPattern,
)


class CalendarConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class WorkingDaysResult:
    days: Decimal
    policy_version_id: int
    work_pattern_ids: tuple[int, ...]


def _scope_fields(scope: str, *, company=None, site=None, department=None, employee=None) -> dict:
    selectors = {
        "organization": {},
        "company": {"company": company},
        "site": {"company": company, "site": site},
        "department": {"company": company, "department": department},
        "employee": {"company": company, "employee": employee},
    }
    if scope not in selectors:
        raise ValidationError({"scope": "دامنه نامعتبر است"})
    fields = selectors[scope]
    if any(value is None for value in fields.values()):
        raise ValidationError({"scope": "محدوده سازمانی برای این دامنه الزامی است"})
    return {f"{key}_id": value.pk for key, value in fields.items()}


@transaction.atomic
def create_work_pattern(*, actor, name: str, company, weekdays: list[int], start_time: dt.time,
                        end_time: dt.time, break_minutes: int, effective_from: dt.date,
                        effective_to: dt.date | None = None, site=None, department=None,
                        employee=None) -> WorkPattern:
    if not name.strip():
        raise ValidationError({"name": "نام الگوی کاری الزامی است"})
    if department and department.company_id != company.pk:
        raise ValidationError({"department": "دپارتمان متعلق به شرکت انتخاب‌شده نیست"})
    if site and site.company_id != company.pk:
        raise ValidationError({"site": "سایت متعلق به شرکت انتخاب‌شده نیست"})
    if employee and employee.company_id != company.pk:
        raise ValidationError({"employee": "کارمند متعلق به شرکت انتخاب‌شده نیست"})

    company.__class__.objects.select_for_update().get(pk=company.pk)
    pattern = WorkPattern(
        name=name.strip(),
        company=company,
        site=site,
        department=department,
        employee=employee,
        working_weekdays=weekdays,
        start_time=start_time,
        end_time=end_time,
        break_minutes=break_minutes,
        effective_from=effective_from,
        effective_to=effective_to,
        created_by=actor,
    )
    pattern.full_clean()
    scope_fields = {
        "company_id": company.pk,
        "site_id": site.pk if site else None,
        "department_id": department.pk if department else None,
        "employee_id": employee.pk if employee else None,
    }
    overlap = WorkPattern.objects.filter(is_active=True, **scope_fields)
    overlap = overlap.filter(effective_from__lte=effective_to) if effective_to else overlap
    overlap = overlap.filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from))
    if overlap.exists():
        raise ValidationError({"effective_from": "برای همین دامنه، الگوی کاری فعال در این بازه وجود دارد"})
    pattern.save()
    AuditEvent.objects.create(
        actor=actor, origin="admin", action="work_pattern.create",
        entity="WorkPattern", entity_id=str(pattern.pk), after={
            "name": pattern.name, "company_id": company.pk, "site_id": pattern.site_id,
            "department_id": pattern.department_id, "employee_id": pattern.employee_id,
            "effective_from": effective_from.isoformat(),
            "effective_to": effective_to.isoformat() if effective_to else None,
        },
    )
    return pattern


def _policy_value_map(values: dict) -> dict:
    required = {key for key in settings_schema.DEFS if key.startswith("policy.")}
    if not isinstance(values, dict) or set(values) != required:
        raise ValidationError({"values": "نسخه سیاست باید همه کلیدهای policy را دقیقاً داشته باشد"})
    normalized = {key: settings_schema.validate_setting(key, value) for key, value in values.items()}
    settings_schema.build_policy({key: settings_schema.to_storable(value)
                                  for key, value in normalized.items()})
    return {key: settings_schema.to_storable(value) for key, value in normalized.items()}


@transaction.atomic
def create_policy_version(*, actor, scope: str, effective_from: dt.date, values: dict,
                           reason: str, company=None, site=None, department=None,
                           employee=None) -> LeavePolicyVersion:
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "دلیل ثبت نسخه سیاست الزامی است"})
    selector_ids = _scope_fields(
        scope, company=company, site=site, department=department, employee=employee,
    )
    if site and site.company_id != company.pk:
        raise ValidationError({"site": "سایت متعلق به شرکت انتخاب‌شده نیست"})
    if department and department.company_id != company.pk:
        raise ValidationError({"department": "دپارتمان متعلق به شرکت انتخاب‌شده نیست"})
    if employee and employee.company_id != company.pk:
        raise ValidationError({"employee": "کارمند متعلق به شرکت انتخاب‌شده نیست"})
    if company:
        Company.objects.select_for_update().get(pk=company.pk)
    else:
        list(Company.objects.select_for_update().order_by("pk").values_list("pk", flat=True))
    stored_values = _policy_value_map(values)
    scope_filter = {"scope": scope, **{
        f"{field}_id": selector_ids.get(f"{field}_id")
        for field in ("company", "site", "department", "employee")
    }}
    existing = LeavePolicyVersion.objects.filter(**scope_filter)
    if existing.filter(effective_from=effective_from).exists():
        raise ValidationError({"effective_from": "برای این دامنه در این تاریخ نسخه‌ای ثبت شده است"})
    version = (existing.aggregate(value=Max("version"))["value"] or 0) + 1
    record = LeavePolicyVersion(
        scope=scope, version=version, effective_from=effective_from,
        values=stored_values, reason=reason, created_by=actor,
        company=company, site=site, department=department, employee=employee,
    )
    record.full_clean()
    record.save()
    AuditEvent.objects.create(
        actor=actor, origin="admin", action="leave_policy.create_version",
        entity="LeavePolicyVersion", entity_id=str(record.pk),
        after={"scope": scope, "version": version, "effective_from": effective_from.isoformat()},
        reason=reason,
    )
    return record


def resolve_policy_version(employee: EmployeeProfile, on_date: dt.date) -> LeavePolicyVersion:
    scopes = [
        ("employee", {"employee_id": employee.pk}),
        ("department", {"department_id": employee.department_id}) if employee.department_id else None,
        ("site", {"site_id": employee.site_id}) if employee.site_id else None,
        ("company", {"company_id": employee.company_id}),
        ("organization", {}),
    ]
    for item in scopes:
        if item is None:
            continue
        scope, selectors = item
        record = LeavePolicyVersion.objects.filter(
            scope=scope, effective_from__lte=on_date, **selectors,
        ).order_by("-effective_from", "-version").first()
        if record:
            return record
    raise CalendarConfigurationError("برای کارمند و تاریخ موردنظر سیاست مرخصی مؤثر ثبت نشده است")


def policy_from_version(version: LeavePolicyVersion) -> LeavePolicy:
    return settings_schema.build_policy(version.values)


def _pattern_priority(pattern: WorkPattern) -> int:
    if pattern.employee_id:
        return 4
    if pattern.department_id:
        return 3
    if pattern.site_id:
        return 2
    return 1


def _patterns_for(employee: EmployeeProfile, start: dt.date, end: dt.date) -> list[WorkPattern]:
    scoped = WorkPattern.objects.filter(
        company_id=employee.company_id, is_active=True, effective_from__lte=end,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=start))
    scope_query = Q(employee_id=employee.pk)
    if employee.department_id:
        scope_query |= Q(department_id=employee.department_id)
    if employee.site_id:
        scope_query |= Q(site_id=employee.site_id)
    scope_query |= Q(site__isnull=True, department__isnull=True, employee__isnull=True)
    return list(scoped.filter(scope_query).select_related("site", "department", "employee"))


def _pattern_for_day(patterns: list[WorkPattern], on_date: dt.date) -> WorkPattern:
    applicable = [
        pattern for pattern in patterns
        if pattern.effective_from <= on_date
        and (pattern.effective_to is None or pattern.effective_to >= on_date)
    ]
    if not applicable:
        raise CalendarConfigurationError(f"برای تاریخ {on_date.isoformat()} الگوی کاری مؤثر تعریف نشده است")
    applicable.sort(key=lambda pattern: (_pattern_priority(pattern), pattern.effective_from, pattern.pk),
                    reverse=True)
    return applicable[0]


def _calendar_holidays(employee: EmployeeProfile, start: dt.date, end: dt.date) -> set[dt.date]:
    scopes = Q(scope__in=["national", "organization"])
    scopes |= Q(scope="company", company_id=employee.company_id)
    if employee.site_id:
        scopes |= Q(scope="site", site_id=employee.site_id)
    ranges = CalendarHoliday.objects.filter(
        scopes, is_active=True, start_date__lte=end, end_date__gte=start,
    ).values_list("start_date", "end_date")
    days: set[dt.date] = set()
    for first, last in ranges:
        day = max(first, start)
        stop = min(last, end)
        while day <= stop:
            days.add(day)
            day += dt.timedelta(days=1)

    scopes_legacy = [employee.company.code]
    if employee.site_id:
        scopes_legacy.append(employee.site.code)
    entries = [
        holiday_rules.HolidayEntry(item.scope, item.jalali_month, item.jalali_day,
                                   item.label, item.jalali_year)
        for item in PublicHoliday.objects.filter(scope__in=["*", *scopes_legacy], is_active=True)
    ]
    days.update(holiday_rules.holidays_in_range(entries, scopes_legacy, start, end))
    return days


def calculate_working_days(*, employee: EmployeeProfile, start: dt.date, end: dt.date,
                           policy_version: LeavePolicyVersion | None = None) -> WorkingDaysResult:
    if start > end:
        raise ValidationError({"end": "پایان بازه باید پس از شروع باشد"})
    policy_version = policy_version or resolve_policy_version(employee, start)
    policy = policy_from_version(policy_version)
    patterns = _patterns_for(employee, start, end)
    holidays = _calendar_holidays(employee, start, end)
    days = [start + dt.timedelta(days=offset) for offset in range((end - start).days + 1)]
    patterns_by_day = {day: _pattern_for_day(patterns, day) for day in days}

    def is_working(day: dt.date) -> bool:
        pattern = patterns_by_day[day]
        return day not in holidays and day.weekday() in pattern.working_weekdays

    working_dates = [day for day in days if is_working(day)]
    if not working_dates:
        count = Decimal("0")
    else:
        first, last = working_dates[0], working_dates[-1]
        count = Decimal("0")
        for day in days:
            if day < first or day > last or day in holidays:
                continue
            pattern = patterns_by_day[day]
            if day.weekday() in pattern.working_weekdays:
                count += Decimal("1")
            elif (day.weekday() in policy.weekly_off_weekdays and
                  policy.leave_day_counting == "INCLUDE_WEEKLY_OFF_INSIDE"):
                count += Decimal("1")

    used_patterns = tuple(sorted({patterns_by_day[day].pk for day in days}))
    return WorkingDaysResult(count, policy_version.pk, used_patterns)


def calculate_working_minutes(*, employee: EmployeeProfile, on_date: dt.date) -> int:
    pattern = _pattern_for_day(_patterns_for(employee, on_date, on_date), on_date)
    if on_date.weekday() not in pattern.working_weekdays or on_date in _calendar_holidays(employee, on_date, on_date):
        return 0
    return pattern.daily_work_minutes


def holiday_snapshot(holiday: CalendarHoliday) -> dict:
    return {
        "title": holiday.title,
        "start_date": holiday.start_date.isoformat(),
        "end_date": holiday.end_date.isoformat(),
        "scope": holiday.scope,
        "company_id": holiday.company_id,
        "site_id": holiday.site_id,
        "holiday_kind": holiday.holiday_kind,
        "description": holiday.description,
        "source": holiday.source,
        "is_active": holiday.is_active,
    }


@transaction.atomic
def create_calendar_holiday(*, actor, **fields) -> CalendarHoliday:
    holiday = CalendarHoliday(created_by=actor, updated_by=actor, **fields)
    holiday.full_clean()
    holiday.save()
    snapshot = holiday_snapshot(holiday)
    CalendarHolidayHistory.objects.create(
        holiday_id=holiday.pk, action="create", before=None, after=snapshot, actor=actor,
    )
    AuditEvent.objects.create(
        actor=actor, origin="admin", action="calendar_holiday.create",
        entity="CalendarHoliday", entity_id=str(holiday.pk), after=snapshot,
    )
    return holiday


@transaction.atomic
def update_calendar_holiday(*, actor, holiday_id: int, changes: dict) -> CalendarHoliday:
    holiday = CalendarHoliday.objects.select_for_update().get(pk=holiday_id)
    before = holiday_snapshot(holiday)
    for key, value in changes.items():
        if key in {"id", "created_by_id", "created_at", "updated_at"}:
            raise ValidationError({key: "این فیلد قابل تغییر نیست"})
        setattr(holiday, key, value)
    holiday.updated_by = actor
    holiday.full_clean()
    holiday.save()
    after = holiday_snapshot(holiday)
    CalendarHolidayHistory.objects.create(
        holiday_id=holiday.pk, action="update", before=before, after=after, actor=actor,
    )
    AuditEvent.objects.create(
        actor=actor, origin="admin", action="calendar_holiday.update",
        entity="CalendarHoliday", entity_id=str(holiday.pk), before=before, after=after,
    )
    return holiday


@transaction.atomic
def deactivate_calendar_holiday(*, actor, holiday_id: int, reason: str) -> None:
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "دلیل غیرفعال‌سازی الزامی است"})
    holiday = CalendarHoliday.objects.select_for_update().get(pk=holiday_id)
    before = holiday_snapshot(holiday)
    holiday.is_active = False
    holiday.updated_by = actor
    holiday.save(update_fields=["is_active", "updated_by", "updated_at"])
    after = holiday_snapshot(holiday)
    CalendarHolidayHistory.objects.create(
        holiday_id=holiday.pk, action="deactivate", before=before, after=after, actor=actor,
    )
    AuditEvent.objects.create(
        actor=actor, origin="admin", action="calendar_holiday.deactivate",
        entity="CalendarHoliday", entity_id=str(holiday.pk), before=before, after=after, reason=reason,
    )
