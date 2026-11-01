import datetime as dt
import unittest
from decimal import Decimal as D
from zsh_core import jalali
from zsh_core.policy import *
from zsh_core.balance import RequestLine, Entitlement, compute_balance

d = dt.date
SAT_WED = {5, 6, 0, 1, 2}          # داده آزمون؛ الگوی واقعی از قرارداد (OQ-02)
SAT_THU = {5, 6, 0, 1, 2, 3}       # داده آزمون
J = LeavePolicy()                  # پیش‌فرض‌های تأییدشده
INC = LeavePolicy(leave_day_counting=COUNT_INCLUDE_WEEKLY_OFF_INSIDE)   # حالت جایگزین قابل تنظیم
G = LeavePolicy(leave_calendar="gregorian")


def jd(y, m, dd):
    return jalali.to_gregorian(y, m, dd)


class PolicyTests(unittest.TestCase):
    def test_defaults_match_user_decisions(self):
        self.assertEqual(J.default_work_weekdays, frozenset({5, 6, 0, 1, 2}))   # OQ-02
        self.assertEqual(J.sick_proration, "months")                            # OQ-19
        self.assertTrue(J.allow_use_before_accrual)                             # OQ-20
        self.assertEqual(J.annual_days_per_month, D("2.5"))
        self.assertEqual(J.sick_days_per_year, D(10))
        self.assertEqual(J.weekly_off_weekdays, frozenset({4}))

    def test_full_year_gives_30_annual_and_10_sick(self):
        s = jd(1390, 1, 1)
        self.assertEqual(annual_base_days(1405, s, None, J), D("30.0"))
        self.assertEqual(sick_base_days(1405, s, None, J), D(10))
        self.assertEqual(annual_base_days(2026, d(2000, 1, 1), None, G), D("30.0"))

    def test_leave_year_bounds_jalali(self):
        self.assertEqual(leave_year_bounds(1405, J), (d(2026, 3, 21), d(2027, 3, 20)))
        self.assertEqual(leave_year_of(d(2026, 3, 20), J), 1404)
        self.assertEqual(leave_year_of(d(2026, 3, 21), J), 1405)

    def test_proration_modes_mid_month_hire(self):
        start = jd(1405, 7, 16)   # ۱۶ مهر ۱۴۰۵ (مهر ۳۰ روز → ۱۵ روز از ماه)
        # ماه‌های بعد: آبان…اسفند = ۵ ماه کامل + نصف مهر (۱۵ از ۳۰ روز)
        self.assertEqual(service_months_in_year(1405, start, None, J), D("5.5"))
        self.assertEqual(annual_base_days(1405, start, None, J), D("13.8"))   # 5.5×2.5=13.75→13.8
        self.assertEqual(service_months_in_year(1405, start, None, LeavePolicy(partial_month_mode=PARTIAL_FLOOR)), D(5))
        self.assertEqual(service_months_in_year(1405, start, None, LeavePolicy(partial_month_mode=PARTIAL_ROUND_UP)), D(6))

    def test_mid_year_leaver_and_not_yet_hired(self):
        s, e = jd(1390, 1, 1), jd(1405, 6, 31)   # پایان شهریور
        self.assertEqual(service_months_in_year(1405, s, e, J), D(6))
        self.assertEqual(annual_base_days(1405, jd(1406, 1, 1), None, J), D("0.0"))
        self.assertEqual(sick_base_days(1405, jd(1406, 1, 1), None, J), D(0))
        self.assertEqual(sick_base_days(1405, s, jd(1404, 12, 29), J), D(0))

    def test_sick_proration(self):
        start = jd(1405, 7, 16)                                   # ۵٫۵ ماه خدمت
        self.assertEqual(sick_base_days(1405, start, None, J), D("4.6"))   # 10×5.5/12=4.583→4.6
        flat = LeavePolicy(sick_proration="none")
        self.assertEqual(sick_base_days(1405, start, None, flat), D(10))
        self.assertEqual(sick_base_days(1405, jd(1390, 1, 1), None, J), D(10))

    def test_booking_cap_before_accrual(self):
        start, asof = jd(1390, 1, 1), jd(1405, 3, 31)             # پایان خرداد → ۳ ماه تحقق
        acc = accrued_annual_to_date(1405, start, None, asof, J)
        self.assertEqual(acc, D("7.5"))
        self.assertEqual(bookable_cap_adjustment(D(30), acc, J), D(0))        # پیش‌فرض: مجاز
        strict = LeavePolicy(allow_use_before_accrual=False)
        self.assertEqual(bookable_cap_adjustment(D(30), acc, strict), D("22.5"))
        self.assertEqual(accrued_annual_to_date(1405, jd(1405, 6, 1), None, jd(1405, 3, 1), J), D(0))

    def test_invalid_policy_and_service(self):
        with self.assertRaises(PolicyError):
            LeavePolicy(sick_proration="x")
        with self.assertRaises(PolicyError):
            LeavePolicy(default_work_weekdays=frozenset({9}))
        with self.assertRaises(PolicyError):
            LeavePolicy(leave_calendar="x")
        with self.assertRaises(PolicyError):
            LeavePolicy(annual_days_per_month=D(-1))
        with self.assertRaises(PolicyError):
            service_months_in_year(1405, d(2026, 5, 2), d(2026, 5, 1), J)

    def test_count_includes_friday_inside_leave(self):
        # یکشنبه ۱۱-۰۱ تا چهارشنبه ۱۱-۱۱ (شامل جمعه ۱۱-۰۶ و پنجشنبه ۱۱-۰۵)
        n = count_leave_days(d(2026, 11, 1), d(2026, 11, 11), SAT_WED, [], INC)
        # روزهای کاری: ۱,۲,۳,۴ + ۷,۸,۹,۱۰,۱۱ = 9 ؛ جمعه ۶ داخل = +۱ ؛ پنجشنبه ۵ شرکتی = ۰
        self.assertEqual(n, D(10))

    def test_default_counting_is_working_days_only(self):   # OQ-18: خیر
        self.assertEqual(count_leave_days(d(2026, 11, 1), d(2026, 11, 11), SAT_WED, [], J), D(9))
        self.assertEqual(count_leave_days(d(2026, 11, 1), d(2026, 11, 11), SAT_WED, [], INC), D(10))

    def test_boundary_non_working_days_trimmed(self):
        # شروع از جمعه ۱۱-۰۶ تا شنبه ۱۱-۰۷ → فقط شنبه
        self.assertEqual(count_leave_days(d(2026, 11, 6), d(2026, 11, 7), SAT_WED, [], J), D(1))
        # فقط جمعه
        self.assertEqual(count_leave_days(d(2026, 11, 6), d(2026, 11, 6), SAT_WED, [], J), D(0))

    def test_official_holiday_inside_not_counted(self):
        n = count_leave_days(d(2026, 11, 1), d(2026, 11, 11), SAT_WED, [d(2026, 11, 8)], INC)
        self.assertEqual(n, D(9))
        # تعطیل رسمی که جمعه نیست و روز کاری است
        # تعطیل رسمی روی جمعه هم دوباره‌شماری نمی‌شود
        n2 = count_leave_days(d(2026, 11, 1), d(2026, 11, 11), SAT_WED, [d(2026, 11, 6)], INC)
        self.assertEqual(n2, D(9))

    def test_thursday_workday_pattern(self):
        n = count_leave_days(d(2026, 11, 1), d(2026, 11, 11), SAT_THU, [], INC)
        self.assertEqual(n, D(11))   # ۱–۵ + ۷–۱۱ کاری = ۱۰ ؛ جمعه = +۱

    def test_count_errors(self):
        with self.assertRaises(PolicyError):
            count_leave_days(d(2026, 11, 3), d(2026, 11, 1), SAT_WED, [], J)
        with self.assertRaises(PolicyError):
            count_leave_days(d(2026, 11, 1), d(2026, 11, 3), set(), [], J)

    def test_balance_with_jalali_leave_year(self):
        # مرخصی ۲۰–۲۴ اسفند ۱۴۰۴ تا ۴–۷ فروردین ۱۴۰۵ (رد شدن از مرز سال شمسی)
        ln = RequestLine("APPROVED", jd(1404, 12, 28), jd(1405, 1, 8), D(8))
        y = lambda x: leave_year_of(x, J)
        b04 = compute_balance(Entitlement(D(30)), [ln], 1404, year_of=y)
        b05 = compute_balance(Entitlement(D(30)), [ln], 1405, year_of=y)
        self.assertEqual(b04.used + b05.used, D(8))
        self.assertTrue(b04.used > 0 and b05.used > 0)


if __name__ == "__main__":
    unittest.main()
