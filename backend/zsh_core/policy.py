"""سیاست مرخصی قابل پیکربندی + محاسبه سهمیه پایه و شمارش روز مصرف‌شده.

همه عددها پیش‌فرض‌اند و باید از تنظیمات (SystemSetting/LeavePolicy) بیایند:
- استحقاقی ۲٫۵ روز به‌ازای هر ماه خدمت (تأیید کاربر)
- استعلاجی ۱۰ روز در سال (تأیید کاربر)
- تعطیل هفتگی: جمعه (قانون کار ماده ۶۲)
- شمول جمعه‌ها در مرخصی: طبق ماده ۶۴ «با احتساب چهار روز جمعه» → پیش‌فرض INCLUDE (نیازمند تأیید حقوقی)
هیچ تعطیلی رسمی در کد ثابت نیست؛ داده تعطیلات از منبع رسمی بارگذاری می‌شود.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Collection

from . import jalali

FRIDAY = 4  # Python weekday: Monday=0 … Sunday=6
_TENTH = Decimal("0.1")

COUNT_WORKING_ONLY = "WORKING_DAYS_ONLY"
COUNT_INCLUDE_WEEKLY_OFF_INSIDE = "INCLUDE_WEEKLY_OFF_INSIDE"
PARTIAL_PRORATE = "prorate_by_day"
PARTIAL_FLOOR = "floor"
PARTIAL_ROUND_UP = "round_up"


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class LeavePolicy:
    leave_calendar: str = "jalali"                 # jalali | gregorian  (فرض A-7؛ OQ-16)
    annual_days_per_month: Decimal = Decimal("2.5")
    sick_days_per_year: Decimal = Decimal("10")
    partial_month_mode: str = PARTIAL_PRORATE      # فرض A-8؛ OQ-17
    weekly_off_weekdays: frozenset = frozenset({FRIDAY})
    default_work_weekdays: frozenset = frozenset({5, 6, 0, 1, 2})   # شنبه تا چهارشنبه (OQ-02: پنجشنبه کاری نیست)
    leave_day_counting: str = COUNT_WORKING_ONLY   # OQ-18: خیر → جمعه‌های داخل مرخصی مصرف سهمیه نیستند
    sick_proration: str = "months"                 # OQ-19: بله → متناسب با ماه‌های خدمت
    allow_use_before_accrual: bool = True          # OQ-20: بله → کل سهمیه سال از ابتدا قابل رزرو

    def __post_init__(self):
        if self.leave_calendar not in ("jalali", "gregorian"):
            raise PolicyError("تقویم سال مرخصی نامعتبر")
        if self.partial_month_mode not in (PARTIAL_PRORATE, PARTIAL_FLOOR, PARTIAL_ROUND_UP):
            raise PolicyError("حالت ماه ناقص نامعتبر")
        if self.leave_day_counting not in (COUNT_WORKING_ONLY, COUNT_INCLUDE_WEEKLY_OFF_INSIDE):
            raise PolicyError("حالت شمارش روز مرخصی نامعتبر")
        if self.sick_proration not in ("none", "months"):
            raise PolicyError("حالت تناسب استعلاجی نامعتبر")
        if self.annual_days_per_month < 0 or self.sick_days_per_year < 0:
            raise PolicyError("مقدار سهمیه نمی‌تواند منفی باشد")
        for name in ("weekly_off_weekdays", "default_work_weekdays"):
            v = getattr(self, name)
            if any((not isinstance(x, int)) or not 0 <= x <= 6 for x in v):
                raise PolicyError(f"{name}: روز هفته نامعتبر")


# ───────── سال مرخصی ─────────
def leave_year_of(d: dt.date, policy: LeavePolicy) -> int:
    return jalali.from_gregorian(d)[0] if policy.leave_calendar == "jalali" else d.year


def _month_ranges(year: int, policy: LeavePolicy) -> list[tuple[dt.date, dt.date]]:
    out = []
    for m in range(1, 13):
        if policy.leave_calendar == "jalali":
            s = jalali.to_gregorian(year, m, 1)
            e = jalali.to_gregorian(year, m, jalali.month_length(year, m))
        else:
            s = dt.date(year, m, 1)
            e = (dt.date(year + (m == 12), (m % 12) + 1, 1) - dt.timedelta(days=1))
        out.append((s, e))
    return out


def leave_year_bounds(year: int, policy: LeavePolicy) -> tuple[dt.date, dt.date]:
    r = _month_ranges(year, policy)
    return r[0][0], r[-1][1]


# ───────── سهمیه پایه ─────────
def service_months_in_year(year: int, service_start: dt.date, service_end: dt.date | None,
                           policy: LeavePolicy) -> Decimal:
    """ماه‌های خدمت در سال مرخصی طبق حالت ماه ناقص (ماده ۶۴: تناسب با مدت کار)."""
    if service_end is not None and service_end < service_start:
        raise PolicyError("پایان همکاری قبل از شروع است")
    total = Decimal("0")
    for ms, me in _month_ranges(year, policy):
        lo, hi = max(ms, service_start), min(me, service_end or me)
        if lo > hi:
            continue
        days_in = (hi - lo).days + 1
        days_month = (me - ms).days + 1
        if policy.partial_month_mode == PARTIAL_PRORATE:
            total += Decimal(days_in) / Decimal(days_month)
        elif policy.partial_month_mode == PARTIAL_FLOOR:
            total += Decimal(1) if days_in == days_month else Decimal(0)
        else:
            total += Decimal(1)
    return total


def annual_base_days(year: int, service_start: dt.date, service_end: dt.date | None,
                     policy: LeavePolicy) -> Decimal:
    months = service_months_in_year(year, service_start, service_end, policy)
    return (months * policy.annual_days_per_month).quantize(_TENTH, ROUND_HALF_UP)


def sick_base_days(year: int, service_start: dt.date, service_end: dt.date | None,
                   policy: LeavePolicy) -> Decimal:
    """استعلاجی: سالانه؛ در حالت sick_proration='months' متناسب با ماه‌های خدمت (OQ-19)."""
    lo, hi = leave_year_bounds(year, policy)
    if service_start > hi or (service_end is not None and service_end < lo):
        return Decimal("0")
    if policy.sick_proration == "none":
        return policy.sick_days_per_year
    months = service_months_in_year(year, service_start, service_end, policy)
    return (policy.sick_days_per_year * months / Decimal(12)).quantize(_TENTH, ROUND_HALF_UP)


def accrued_annual_to_date(year: int, service_start: dt.date, service_end: dt.date | None,
                           as_of: dt.date, policy: LeavePolicy) -> Decimal:
    """مقدار استحقاق تحقق‌یافته تا as_of (برای حالتی که رزرو پیش از تحقق مجاز نباشد)."""
    end = as_of if service_end is None else min(service_end, as_of)
    if end < service_start:
        return Decimal("0")
    return annual_base_days(year, service_start, end, policy)


def bookable_cap_adjustment(base_days: Decimal, accrued_to_date: Decimal, policy: LeavePolicy) -> Decimal:
    """مقداری که باید از «قابل استفاده» کم شود تا رزرو فقط تا سقف تحقق‌یافته باشد.
    اگر allow_use_before_accrual=True صفر است (OQ-20)."""
    if policy.allow_use_before_accrual:
        return Decimal("0")
    return max(base_days - accrued_to_date, Decimal("0"))


# ───────── شمارش روز مصرف‌شده ─────────
def count_leave_days(start: dt.date, end: dt.date, work_weekdays: Collection[int],
                     holidays: Collection[dt.date], policy: LeavePolicy) -> Decimal:
    """پیشنهاد تعداد روز مصرف‌شده از سهمیه (تخمین؛ کاربر/مدیر قابل اصلاح).

    ابتدا روزهای غیرکاری ابتدا/انتهای بازه حذف می‌شوند. سپس در داخل بازه:
    تعطیل رسمی → شمرده نمی‌شود؛ روز کاری → ۱؛ تعطیل هفتگی → ۱ فقط در حالت INCLUDE؛
    سایر روزهای غیرکاری قرارداد (مثلاً پنجشنبه تعطیل شرکتی) → شمرده نمی‌شود.
    """
    if start > end:
        raise PolicyError("تاریخ شروع نباید بعد از پایان باشد")
    if not work_weekdays:
        raise PolicyError("الگوی روزهای کاری تعریف نشده است")
    hol = set(holidays)
    ww = set(work_weekdays)
    is_work = lambda x: x.weekday() in ww and x not in hol
    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    work_days = [d for d in days if is_work(d)]
    if not work_days:
        return Decimal("0")
    first, last = work_days[0], work_days[-1]
    n = Decimal("0")
    for d in days:
        if d < first or d > last or d in hol:
            continue
        if d.weekday() in ww:
            n += 1
        elif d.weekday() in policy.weekly_off_weekdays and \
                policy.leave_day_counting == COUNT_INCLUDE_WEEKLY_OFF_INSIDE:
            n += 1
    return n
