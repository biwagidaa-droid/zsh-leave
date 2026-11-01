"""تبدیل تقویم شمسی ↔ میلادی (لایه مشترک و یگانه).

قاعده کبیسه: چرخه ۳۳ ساله (سال‌های با باقی‌مانده 1,5,9,13,17,22,26,30 کبیسه‌اند).
این قاعده حسابی با تقویم رسمی ایران فقط در یک بازه محدود هم‌خوان است؛
خارج از بازه پشتیبانی‌شده خطا می‌دهد تا خطای بی‌صدا رخ ندهد.
لنگر: ۱ فروردین ۱۴۰۰ = ۲۰۲۱-۰۳-۲۱.
"""
from __future__ import annotations

import datetime as _dt
from functools import lru_cache

MIN_YEAR, MAX_YEAR = 1343, 1472
_LEAP_REMAINDERS = frozenset({1, 5, 9, 13, 17, 22, 26, 30})
_ANCHOR_YEAR = 1400
_ANCHOR_DATE = _dt.date(2021, 3, 21)
MONTH_NAMES = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
               "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


class JalaliError(ValueError):
    pass


def is_leap(jy: int) -> bool:
    return jy % 33 in _LEAP_REMAINDERS


def year_length(jy: int) -> int:
    return 366 if is_leap(jy) else 365


def month_length(jy: int, jm: int) -> int:
    if not 1 <= jm <= 12:
        raise JalaliError(f"ماه نامعتبر: {jm}")
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if is_leap(jy) else 29


def _check_year(jy: int) -> None:
    if not MIN_YEAR <= jy <= MAX_YEAR:
        raise JalaliError(f"سال {jy} خارج از بازه پشتیبانی‌شده {MIN_YEAR}–{MAX_YEAR} است")


@lru_cache(maxsize=None)
def _year_start(jy: int) -> _dt.date:
    """تاریخ میلادی اول فروردین سال jy."""
    d = _ANCHOR_DATE
    if jy >= _ANCHOR_YEAR:
        for y in range(_ANCHOR_YEAR, jy):
            d += _dt.timedelta(days=year_length(y))
    else:
        for y in range(_ANCHOR_YEAR - 1, jy - 1, -1):
            d -= _dt.timedelta(days=year_length(y))
    return d


def to_gregorian(jy: int, jm: int, jd: int) -> _dt.date:
    _check_year(jy)
    if not 1 <= jd <= month_length(jy, jm):
        raise JalaliError(f"روز نامعتبر: {jy}/{jm}/{jd}")
    offset = sum(month_length(jy, m) for m in range(1, jm)) + (jd - 1)
    return _year_start(jy) + _dt.timedelta(days=offset)


def from_gregorian(d: _dt.date) -> tuple[int, int, int]:
    jy = d.year - 622                       # حدس اولیه؛ سپس تصحیح دقیق (بدون وابستگی به بازه)
    while _year_start(jy) > d:
        jy -= 1
    while _year_start(jy + 1) <= d:
        jy += 1
    _check_year(jy)
    days = (d - _year_start(jy)).days
    for jm in range(1, 13):
        ml = month_length(jy, jm)
        if days < ml:
            return jy, jm, days + 1
        days -= ml
    raise JalaliError("خطای داخلی تبدیل تاریخ")  # pragma: no cover


def format_jalali(d: _dt.date, with_month_name: bool = False) -> str:
    jy, jm, jd = from_gregorian(d)
    if with_month_name:
        return f"{jd} {MONTH_NAMES[jm - 1]} {jy}"
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def parse_jalali(text: str) -> _dt.date:
    """ورودی 'YYYY/MM/DD' (ارقام فارسی/عربی هم پذیرفته می‌شود)."""
    table = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    parts = text.strip().translate(table).replace("-", "/").split("/")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise JalaliError("قالب تاریخ باید سال/ماه/روز باشد")
    return to_gregorian(*(int(p) for p in parts))
