"""سرویس‌های داشبورد مدیریت: تنظیمات و تعطیلات. هر تغییر اعتبارسنجی، تراکنشی و حسابرسی می‌شود."""
from __future__ import annotations

from django.db import transaction

from zsh_core import holidays as H
from zsh_core import settings_schema as S
from zsh_core.policy import LeavePolicy
from .models import AuditEvent, PublicHoliday, PublicHolidayHistory, SystemSetting


def load_settings() -> dict:
    stored = {s.key: s.value for s in SystemSetting.objects.all()}
    # مقدارهای ذخیره‌شده دوباره اعتبارسنجی می‌شوند؛ مقدار خراب خطا می‌دهد (نادیده گرفته نمی‌شود)
    return S.resolve(stored)


def load_policy() -> LeavePolicy:
    return S.build_policy({s.key: s.value for s in SystemSetting.objects.all()})


@transaction.atomic
def set_setting(*, user, key: str, value, reason: str) -> dict:
    if not (reason or "").strip():
        raise S.SettingError("درج دلیل تغییر الزامی است")
    normalized = S.validate_setting(key, value)
    # سازگاری کل سیاست پس از تغییر بررسی می‌شود (مثلاً ترکیب نامعتبر)
    current = {s.key: s.value for s in SystemSetting.objects.select_for_update().all()}
    candidate = dict(current)
    candidate[key] = S.to_storable(normalized)
    S.build_policy(candidate)
    obj, _ = SystemSetting.objects.select_for_update().get_or_create(key=key)
    before = obj.value
    obj.value, obj.updated_by = S.to_storable(normalized), user
    obj.save()
    AuditEvent.objects.create(actor=user, origin="admin", action="setting.update",
                              entity="SystemSetting", entity_id=key,
                              before={"value": before}, after={"value": obj.value}, reason=reason)
    return {key: normalized}


def _entry_of(h: PublicHoliday) -> H.HolidayEntry:
    return H.HolidayEntry(h.scope, h.jalali_month, h.jalali_day, h.label, h.jalali_year)


def _snapshot(h: PublicHoliday) -> dict:
    return {"scope": h.scope, "year": h.jalali_year, "month": h.jalali_month,
            "day": h.jalali_day, "label": h.label}


@transaction.atomic
def add_holiday(*, user, scope: str, label: str, jalali_text: str, recurring: bool) -> PublicHoliday:
    entry = H.make_entry_from_text(scope, label, jalali_text, recurring)      # خطای قالب/تاریخ
    existing = [_entry_of(h) for h in PublicHoliday.objects.select_for_update().filter(scope=entry.scope)]
    years = {entry.jalali_year} if entry.jalali_year else {1403, 1404, 1405, 1406}
    H.check_duplicates(existing + [entry], years)
    h = PublicHoliday.objects.create(scope=entry.scope, jalali_year=entry.jalali_year,
                                     jalali_month=entry.jalali_month, jalali_day=entry.jalali_day,
                                     label=entry.label, created_by=user)
    PublicHolidayHistory.objects.create(holiday_id=h.pk, action="create", before=None,
                                        after=_snapshot(h), actor=user)
    AuditEvent.objects.create(actor=user, origin="admin", action="holiday.create",
                              entity="PublicHoliday", entity_id=str(h.pk), after=_snapshot(h))
    return h


@transaction.atomic
def delete_holiday(*, user, holiday_id: int, reason: str) -> None:
    if not (reason or "").strip():
        raise H.HolidayError("درج دلیل حذف الزامی است")
    h = PublicHoliday.objects.select_for_update().get(pk=holiday_id)
    snap = _snapshot(h)
    PublicHolidayHistory.objects.create(holiday_id=h.pk, action="delete", before=snap, after=None, actor=user)
    AuditEvent.objects.create(actor=user, origin="admin", action="holiday.delete",
                              entity="PublicHoliday", entity_id=str(h.pk), before=snap, reason=reason)
    h.delete()


def entries_for(scopes) -> list[H.HolidayEntry]:
    return [_entry_of(h) for h in PublicHoliday.objects.filter(scope__in=list(scopes) + ["*"])]
