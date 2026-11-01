"""تعریف و اعتبارسنجی تنظیمات قابل ویرایش در داشبورد مدیریت.

هر کلید: نوع، پیش‌فرض، اعتبارسنجی، توضیح فارسی. مقدارهای تصمیم‌نگرفته‌شده سازمان
پیش‌فرض None دارند (= پیکربندی نشده؛ قابلیت وابسته غیرفعال می‌ماند) و عدد ساختگی نمی‌گیرند.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from .policy import (LeavePolicy, PolicyError, COUNT_INCLUDE_WEEKLY_OFF_INSIDE, COUNT_WORKING_ONLY,
                     PARTIAL_FLOOR, PARTIAL_PRORATE, PARTIAL_ROUND_UP)


class SettingError(ValueError):
    pass


def _decimal(lo: str, hi: str):
    def f(v):
        try:
            d = Decimal(str(v))
        except (InvalidOperation, ValueError):
            raise SettingError("عدد معتبر نیست")
        if not d.is_finite() or not Decimal(lo) <= d <= Decimal(hi):
            raise SettingError(f"مقدار باید بین {lo} و {hi} باشد")
        return d
    return f


def _enum(*choices):
    def f(v):
        if v not in choices:
            raise SettingError(f"یکی از {list(choices)} را انتخاب کنید")
        return v
    return f


def _weekdays(v):
    if not isinstance(v, (list, tuple, set, frozenset)) or isinstance(v, str):
        raise SettingError("فهرست روزهای هفته لازم است")
    out = set()
    for x in v:
        if isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= 6:
            raise SettingError("روز هفته باید عدد ۰ (دوشنبه) تا ۶ (یکشنبه) باشد")
        out.add(x)
    if not out:
        raise SettingError("حداقل یک روز لازم است")
    return frozenset(out)


def _bool(v):
    if not isinstance(v, bool):
        raise SettingError("مقدار باید درست/نادرست باشد")
    return v


def _int_range(v, lo: int, hi: int):
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise SettingError(f"عدد صحیح بین {lo} و {hi}")
    return v


def _opt_int(lo: int, hi: int):
    def f(v):
        if v is None:
            return None
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise SettingError(f"عدد صحیح بین {lo} و {hi} یا خالی")
        return v
    return f


@dataclass(frozen=True)
class SettingDef:
    key: str
    default: Any
    validate: Callable[[Any], Any]
    label_fa: str
    group: str
    sensitive_change: bool = True     # تغییر → AuditEvent


_DEFS = [
    SettingDef("policy.leave_calendar", "jalali", _enum("jalali", "gregorian"), "تقویم سال مرخصی", "policy"),
    SettingDef("policy.annual_days_per_month", Decimal("2.5"), _decimal("0", "10"),
               "روز مرخصی استحقاقی به‌ازای هر ماه خدمت", "policy"),
    SettingDef("policy.sick_days_per_year", Decimal("10"), _decimal("0", "366"),
               "روز مرخصی استعلاجی در سال", "policy"),
    SettingDef("policy.sick_proration", "months", _enum("none", "months"),
               "تناسب استعلاجی با ماه‌های خدمت", "policy"),
    SettingDef("policy.partial_month_mode", PARTIAL_PRORATE,
               _enum(PARTIAL_PRORATE, PARTIAL_FLOOR, PARTIAL_ROUND_UP), "محاسبه ماه ناقص", "policy"),
    SettingDef("policy.weekly_off_weekdays", frozenset({4}), _weekdays, "تعطیل هفتگی", "policy"),
    SettingDef("policy.default_work_weekdays", frozenset({5, 6, 0, 1, 2}), _weekdays,
               "الگوی پیش‌فرض روزهای کاری (در نبود قرارداد)", "policy"),
    SettingDef("policy.leave_day_counting", COUNT_WORKING_ONLY,
               _enum(COUNT_WORKING_ONLY, COUNT_INCLUDE_WEEKLY_OFF_INSIDE),
               "شمارش روز مرخصی (فقط روز کاری / با جمعه‌های داخل مرخصی)", "policy"),
    SettingDef("policy.allow_use_before_accrual", True, _bool,
               "امکان استفاده از سهمیه پیش از تحقق ماهانه", "policy"),
    SettingDef("privacy.employee_sees_own_confidential_type", False, _bool,
               "کارمند نوع مرخصی محرمانه خودش را ببیند (پیش‌فرض: خیر، مطابق مرجع)", "privacy"),
    SettingDef("privacy.peers_see_leave_type", False, _bool,
               "همکاران نوع مرخصی را در تقویم ببینند (پیش‌فرض: فقط «غایب»)", "privacy"),
    SettingDef("privacy.min_group_size", 5, lambda v: _int_range(v, 2, 100),
               "حداقل اندازه گروه در گزارش تجمیعی (پیش‌فرض ۵؛ نیازمند تأیید سازمان)", "privacy"),
    # تصمیم‌نگرفته (OQ-04): None = غیرفعال
    SettingDef("workflow.reminder_after_working_days", None, _opt_int(0, 60),
               "یادآوری به مدیر پس از N روز کاری (خالی = غیرفعال)", "workflow"),
    SettingDef("workflow.escalate_after_working_days", None, _opt_int(1, 60),
               "ارجاع خودکار به HR پس از N روز کاری (خالی = غیرفعال)", "workflow"),
    SettingDef("holidays.source", "manual", _enum("manual"), "منبع تعطیلات (ثبت دستی توسط مدیر)", "holidays"),
]
DEFS: dict[str, SettingDef] = {d.key: d for d in _DEFS}


def validate_setting(key: str, value: Any) -> Any:
    d = DEFS.get(key)
    if d is None:
        raise SettingError(f"کلید ناشناخته: {key}")
    return d.validate(value)


def defaults() -> dict[str, Any]:
    return {k: d.default for k, d in DEFS.items()}


def resolve(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """پیش‌فرض‌ها + مقدارهای ذخیره‌شده (هر مقدار دوباره اعتبارسنجی می‌شود؛ مقدار خراب → خطا، نه نادیده‌گرفتن)."""
    out = defaults()
    for k, v in (overrides or {}).items():
        out[k] = validate_setting(k, v)
    return out


def to_storable(value: Any) -> Any:
    """تبدیل به JSON (Decimal→str، frozenset→لیست مرتب)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    return value


def build_policy(values: dict[str, Any]) -> LeavePolicy:
    v = resolve(values)
    try:
        return LeavePolicy(
            leave_calendar=v["policy.leave_calendar"],
            annual_days_per_month=v["policy.annual_days_per_month"],
            sick_days_per_year=v["policy.sick_days_per_year"],
            sick_proration=v["policy.sick_proration"],
            partial_month_mode=v["policy.partial_month_mode"],
            weekly_off_weekdays=v["policy.weekly_off_weekdays"],
            default_work_weekdays=v["policy.default_work_weekdays"],
            leave_day_counting=v["policy.leave_day_counting"],
            allow_use_before_accrual=v["policy.allow_use_before_accrual"],
        )
    except PolicyError as e:
        raise SettingError(str(e))
