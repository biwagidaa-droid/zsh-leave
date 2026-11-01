"""محاسبه مانده مرخصی (تابع خالص، بدون پایگاه داده).

کل = پایه + انتقال + اصلاح دستی
استفاده‌شده = جمع روز با وضعیت APPROVED یا WITHDRAWAL_PENDING   (فرض C-3)
در انتظار = جمع روز با وضعیت PENDING یا ESCALATED
مانده = کل − استفاده‌شده ؛ قابل استفاده = کل − استفاده‌شده − در انتظار
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Iterable

USED_STATUSES = frozenset({"APPROVED", "WITHDRAWAL_PENDING"})
PENDING_STATUSES = frozenset({"PENDING", "ESCALATED"})
_TENTH = Decimal("0.1")


class BalanceError(ValueError):
    pass


@dataclass(frozen=True)
class Entitlement:
    base_days: Decimal
    carry_over_days: Decimal = Decimal("0")
    manual_adjustment: Decimal = Decimal("0")

    @property
    def total(self) -> Decimal:
        return self.base_days + self.carry_over_days + self.manual_adjustment


@dataclass(frozen=True)
class RequestLine:
    status: str
    start: dt.date
    end: dt.date
    working_days: Decimal
    counts_against_balance: bool = True


@dataclass(frozen=True)
class Balance:
    total: Decimal
    used: Decimal
    pending: Decimal

    @property
    def remaining(self) -> Decimal:
        return self.total - self.used

    @property
    def available(self) -> Decimal:
        return self.total - self.used - self.pending


def allocate_by_year(line: RequestLine,
                     is_workday: Callable[[dt.date], bool] | None = None,
                     year_of: Callable[[dt.date], int] = lambda x: x.year) -> dict[int, Decimal]:
    """سهم هر سال میلادی از روز کاری درخواست.

    فرض (نیازمند تأیید): تقسیم متناسب با تعداد روزهای کاری هر سال در بازه؛
    در نبود تابع is_workday، متناسب با روزهای تقویمی. باقی‌مانده گرد کردن به سال آخر می‌رود.
    year_of: تابع تعیین «سال مرخصی» (پیش‌فرض میلادی؛ سیاست سازمان می‌تواند شمسی بدهد).
    """
    if line.start > line.end:
        raise BalanceError("بازه نامعتبر")
    if line.working_days <= 0:
        raise BalanceError("روز کاری باید مثبت باشد")
    weights: dict[int, int] = {}
    d = line.start
    while d <= line.end:
        if is_workday is None or is_workday(d):
            weights[year_of(d)] = weights.get(year_of(d), 0) + 1
        d += dt.timedelta(days=1)
    if not weights:  # بازه بدون روز کاری؛ همه به سال شروع
        return {year_of(line.start): line.working_days}
    if len(weights) == 1:
        return {next(iter(weights)): line.working_days}
    total_w = sum(weights.values())
    years = sorted(weights)
    out: dict[int, Decimal] = {}
    acc = Decimal("0")
    for y in years[:-1]:
        share = (line.working_days * weights[y] / total_w).quantize(_TENTH, ROUND_HALF_UP)
        out[y] = share
        acc += share
    out[years[-1]] = line.working_days - acc
    return out


def compute_balance(entitlement: Entitlement | None, lines: Iterable[RequestLine],
                    year: int,
                    is_workday: Callable[[dt.date], bool] | None = None,
                    year_of: Callable[[dt.date], int] = lambda x: x.year) -> Balance:
    """اگر سهمیه تعریف نشده باشد، مانده ساختگی نمی‌سازد."""
    if entitlement is None:
        raise BalanceError("برای این کارمند/نوع/سال سهمیه‌ای تعریف نشده است")
    used = pending = Decimal("0")
    for ln in lines:
        if not ln.counts_against_balance:
            continue
        share = allocate_by_year(ln, is_workday, year_of).get(year, Decimal("0"))
        if ln.status in USED_STATUSES:
            used += share
        elif ln.status in PENDING_STATUSES:
            pending += share
        # REJECTED / CANCELLED: بدون اثر
    return Balance(total=entitlement.total, used=used, pending=pending)


def compute_carry_over(prev_remaining: Decimal, policy: str, cap: Decimal | None = None) -> Decimal:
    """policy: none | unlimited | capped. مانده منفی هرگز انتقال مثبت نمی‌دهد."""
    if policy == "none":
        return Decimal("0")
    pos = max(prev_remaining, Decimal("0"))
    if policy == "unlimited":
        return pos
    if policy == "capped":
        if cap is None or cap < 0:
            raise BalanceError("سقف انتقال معتبر نیست")
        return min(pos, cap)
    raise BalanceError(f"سیاست انتقال نامعتبر: {policy}")
