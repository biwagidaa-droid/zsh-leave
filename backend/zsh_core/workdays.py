"""تخمین تعداد روز کاری — فقط «تخمین»؛ مقدار تأییدشده را هرگز بازمحاسبه نمی‌کند."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Collection

# Python: دوشنبه=0 … یکشنبه=6 . الگوی کاری باید از پیکربندی/قرارداد بیاید؛ مقدار پیش‌فرضی وجود ندارد.


class WorkdayError(ValueError):
    pass


@dataclass(frozen=True)
class WorkdayEstimate:
    days: Decimal
    estimated: bool = True  # همیشه True: رابط باید برچسب «تخمین» نشان دهد


def estimate_working_days(start: dt.date, end: dt.date,
                          work_weekdays: Collection[int],
                          holidays: Collection[dt.date] = ()) -> WorkdayEstimate:
    if start > end:
        raise WorkdayError("تاریخ شروع نباید بعد از تاریخ پایان باشد")
    if not work_weekdays:
        raise WorkdayError("الگوی روزهای کاری تعریف نشده است")
    if any(not 0 <= w <= 6 for w in work_weekdays):
        raise WorkdayError("روز هفته نامعتبر")
    hol = set(holidays)
    n, d = 0, start
    while d <= end:
        if d.weekday() in work_weekdays and d not in hol:
            n += 1
        d += dt.timedelta(days=1)
    return WorkdayEstimate(Decimal(n))


def add_working_days(start: dt.date, n: int, work_weekdays: Collection[int],
                     holidays: Collection[dt.date] = ()) -> dt.date:
    """n روز کاری پس از start (برای مهلت‌های «روز کاری»)."""
    if n < 0 or not work_weekdays:
        raise WorkdayError("ورودی نامعتبر")
    hol, d, left = set(holidays), start, n
    while left > 0:
        d += dt.timedelta(days=1)
        if d.weekday() in work_weekdays and d not in hol:
            left -= 1
    return d
