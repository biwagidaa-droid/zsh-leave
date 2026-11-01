import datetime as dt
import unittest
from decimal import Decimal as D
from zsh_core.workdays import estimate_working_days, add_working_days, WorkdayError

d = dt.date
SAT_WED = {5, 6, 0, 1, 2}   # نمونه آزمون: شنبه تا چهارشنبه — الگوی واقعی از پیکربندی می‌آید (OQ-02)


class WorkdayTests(unittest.TestCase):
    def test_estimate_marked_as_estimate(self):
        e = estimate_working_days(d(2026, 11, 1), d(2026, 11, 7), SAT_WED)
        self.assertTrue(e.estimated)

    def test_basic_count(self):
        # ۲۰۲۶-۱۱-۰۱ یکشنبه … ۱۱-۰۷ شنبه ⇒ یکشنبه، دوشنبه، سه‌شنبه، چهارشنبه، شنبه = ۵
        self.assertEqual(estimate_working_days(d(2026, 11, 1), d(2026, 11, 7), SAT_WED).days, D(5))

    def test_holiday_excluded(self):
        e = estimate_working_days(d(2026, 11, 1), d(2026, 11, 7), SAT_WED, [d(2026, 11, 2)])
        self.assertEqual(e.days, D(4))

    def test_holiday_on_weekend_no_effect(self):
        e = estimate_working_days(d(2026, 11, 1), d(2026, 11, 7), SAT_WED, [d(2026, 11, 5)])  # پنجشنبه
        self.assertEqual(e.days, D(5))

    def test_single_day_and_zero(self):
        self.assertEqual(estimate_working_days(d(2026, 11, 5), d(2026, 11, 5), SAT_WED).days, D(0))

    def test_errors(self):
        with self.assertRaises(WorkdayError):
            estimate_working_days(d(2026, 11, 7), d(2026, 11, 1), SAT_WED)
        with self.assertRaises(WorkdayError):
            estimate_working_days(d(2026, 11, 1), d(2026, 11, 2), set())
        with self.assertRaises(WorkdayError):
            estimate_working_days(d(2026, 11, 1), d(2026, 11, 2), {9})

    def test_add_working_days_skips_weekend_and_holidays(self):
        # از چهارشنبه ۱۱-۰۴ سه روز کاری: شنبه ۱۱-۰۷، یکشنبه ۱۱-۰۸، دوشنبه ۱۱-۰۹
        self.assertEqual(add_working_days(d(2026, 11, 4), 3, SAT_WED), d(2026, 11, 9))
        self.assertEqual(add_working_days(d(2026, 11, 4), 3, SAT_WED, [d(2026, 11, 8)]), d(2026, 11, 10))
        self.assertEqual(add_working_days(d(2026, 11, 4), 0, SAT_WED), d(2026, 11, 4))


if __name__ == "__main__":
    unittest.main()
