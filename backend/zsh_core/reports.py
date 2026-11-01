"""توابع خالص گزارش: Bradford Factor (فقط ابزار تحلیلی محرمانه HR)، آمار زمان تصمیم، حذف گروه‌های کوچک."""
from __future__ import annotations

import datetime as dt
import statistics
from typing import Iterable, Mapping


def bradford_factor(spells: Iterable[tuple[dt.date, dt.date]], window_start: dt.date,
                    window_end: dt.date) -> dict:
    """B = S² × D ؛ S تعداد دوره‌های غیبت، D مجموع روزهای تقویمی غیبت در بازه.
    دوره‌های هم‌پوشان/متصل به هم یک دوره حساب می‌شوند (برش به بازه گزارش).
    محدودیت: بدون زمینه پزشکی/قانونی معنای تشخیصی ندارد؛ مبنای تصمیم خودکار نیست."""
    if window_start > window_end:
        raise ValueError("بازه نامعتبر")
    clipped = sorted((max(s, window_start), min(e, window_end)) for s, e in spells
                     if s <= e and s <= window_end and e >= window_start)
    merged: list[list[dt.date]] = []
    for s, e in clipped:
        if merged and s <= merged[-1][1] + dt.timedelta(days=1):
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    S = len(merged)
    D = sum((e - s).days + 1 for s, e in merged)
    return {"spells": S, "days": D, "score": S * S * D,
            "note": "ابزار تحلیلی محرمانه؛ مبنای تصمیم استخدامی/انضباطی/تشخیصی نیست"}


def decision_time_stats(hours: Iterable[float]) -> dict:
    h = sorted(x for x in hours if x is not None and x >= 0)
    if not h:
        return {"count": 0, "mean": None, "median": None}
    return {"count": len(h), "mean": round(statistics.fmean(h), 2), "median": round(statistics.median(h), 2)}


def suppress_small_groups(counts: Mapping[str, int], k: int) -> dict[str, int | None]:
    """گروه‌های کوچکتر از k (و بزرگ‌تر از ۰) به None تبدیل می‌شوند تا افراد قابل شناسایی نباشند.
    توجه: اگر تفاضل با مجموع کل نمایش داده شود، حذف تک‌گروه کافی نیست؛ مجموع هم باید سرکوب/ادغام شود."""
    if k < 2:
        raise ValueError("k باید حداقل ۲ باشد")
    return {name: (None if 0 < c < k else c) for name, c in counts.items()}


def suppress_with_total(counts: Mapping[str, int], k: int) -> tuple[dict[str, int | None], int | None]:
    """سرکوب ثانویه: اگر دقیقاً یک گروه سرکوب شود، کوچک‌ترین گروه بعدی هم سرکوب می‌شود
    و مجموع نمایش داده نمی‌شود، تا از تفاضل نتوان مقدار سرکوب‌شده را فهمید."""
    out = suppress_small_groups(counts, k)
    hidden = [n for n, v in out.items() if v is None]
    if len(hidden) == 1:
        rest = {n: c for n, c in counts.items() if out[n] is not None and c > 0}
        if rest:
            out[min(rest, key=rest.get)] = None
    total = None if any(v is None for v in out.values()) else sum(counts.values())
    return out, total
