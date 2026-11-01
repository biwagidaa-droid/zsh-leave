"""ثبت دستی تعطیلات رسمی با تقویم شمسی (OQ-15). هیچ تاریخ تعطیلی در کد ثابت نیست.

ورودی توسط مدیر؛ هر مدخل یا «یک‌بار» (سال مشخص) یا «سالانه» (ماه/روز شمسی ثابت) است.
تعطیلات قمری/متغیر باید هر سال به‌صورت یک‌بار ثبت شوند.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable

from . import jalali

NATIONAL = "*"


class HolidayError(ValueError):
    pass


@dataclass(frozen=True)
class HolidayEntry:
    scope: str                 # '*' ملی، یا کد شرکت/منطقه
    jalali_month: int
    jalali_day: int
    label: str
    jalali_year: int | None    # None = سالانه (تکرارشونده)

    def resolve(self, jy: int) -> dt.date | None:
        """تاریخ میلادی در سال شمسی jy؛ None اگر برای آن سال وجود ندارد (مثل ۳۰ اسفند در سال غیرکبیسه)."""
        if self.jalali_year is not None and self.jalali_year != jy:
            return None
        if self.jalali_day > jalali.month_length(jy, self.jalali_month):
            return None
        return jalali.to_gregorian(jy, self.jalali_month, self.jalali_day)


def make_entry(scope: str, label: str, jalali_month: int, jalali_day: int,
               jalali_year: int | None = None) -> HolidayEntry:
    label = (label or "").strip()
    if not label or len(label) > 200:
        raise HolidayError("عنوان تعطیلی الزامی و حداکثر ۲۰۰ نویسه است")
    scope = (scope or "").strip()
    if not scope or len(scope) > 64:
        raise HolidayError("دامنه تعطیلی الزامی است ('*' برای ملی)")
    if not 1 <= jalali_month <= 12:
        raise HolidayError("ماه نامعتبر")
    if jalali_year is None:
        if not 1 <= jalali_day <= 31 or jalali_day > jalali.month_length(1404, jalali_month) and \
                not (jalali_month == 12 and jalali_day == 30):
            raise HolidayError("روز نامعتبر برای تعطیلی سالانه")
    else:
        if not jalali.MIN_YEAR <= jalali_year <= jalali.MAX_YEAR:
            raise HolidayError("سال خارج از بازه پشتیبانی‌شده")
        if not 1 <= jalali_day <= jalali.month_length(jalali_year, jalali_month):
            raise HolidayError("روز نامعتبر")
    return HolidayEntry(scope, jalali_month, jalali_day, label, jalali_year)


def make_entry_from_text(scope: str, label: str, text: str, recurring: bool) -> HolidayEntry:
    """text به‌صورت YYYY/MM/DD شمسی؛ recurring=True فقط ماه/روز را نگه می‌دارد."""
    gdate = jalali.parse_jalali(text)          # خطای قالب/محدوده به JalaliError
    jy, jm, jd = jalali.from_gregorian(gdate)
    return make_entry(scope, label, jm, jd, None if recurring else jy)


def _key(e: HolidayEntry, jy: int):
    r = e.resolve(jy)
    return (e.scope, r) if r else None


def check_duplicates(entries: Iterable[HolidayEntry], jyears: Iterable[int]) -> None:
    """دو مدخل با دامنه و تاریخ یکسان در هر سال بررسی‌شده مجاز نیست."""
    entries = list(entries)
    for jy in jyears:
        seen: dict = {}
        for e in entries:
            k = _key(e, jy)
            if k is None:
                continue
            if k in seen:
                raise HolidayError(f"تعطیلی تکراری در دامنه {k[0]} برای {jalali.format_jalali(k[1])}")
            seen[k] = e


def holidays_in_range(entries: Iterable[HolidayEntry], scopes: Iterable[str],
                      start: dt.date, end: dt.date) -> set[dt.date]:
    """مجموعه تاریخ‌های تعطیل میلادی در بازه، برای دامنه‌های مربوط به کارمند (ملی + شرکت/منطقه او)."""
    if start > end:
        raise HolidayError("بازه نامعتبر")
    sc = set(scopes) | {NATIONAL}
    jy0, jy1 = jalali.from_gregorian(start)[0], jalali.from_gregorian(end)[0]
    out: set[dt.date] = set()
    for e in entries:
        if e.scope not in sc:
            continue
        for jy in range(jy0, jy1 + 1):
            r = e.resolve(jy)
            if r and start <= r <= end:
                out.add(r)
    return out


def diff_entries(old: Iterable[HolidayEntry], new: Iterable[HolidayEntry]) -> dict[str, list[HolidayEntry]]:
    """تفاوت برای تاریخچه تغییرات و نمایش تفاوت هنگام تغییر منطقه."""
    o, n = set(old), set(new)
    return {"added": sorted(n - o, key=lambda e: (e.scope, e.jalali_month, e.jalali_day)),
            "removed": sorted(o - n, key=lambda e: (e.scope, e.jalali_month, e.jalali_day))}
