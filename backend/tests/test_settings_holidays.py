import datetime as dt
import unittest
from decimal import Decimal as D
from zsh_core import settings_schema as S
from zsh_core import holidays as H
from zsh_core import jalali
from zsh_core.policy import COUNT_INCLUDE_WEEKLY_OFF_INSIDE


class SettingsTests(unittest.TestCase):
    def test_defaults_reflect_user_decisions(self):
        v = S.defaults()
        self.assertEqual(v["policy.annual_days_per_month"], D("2.5"))
        self.assertEqual(v["policy.sick_days_per_year"], D(10))
        self.assertEqual(v["policy.leave_day_counting"], "WORKING_DAYS_ONLY")
        self.assertEqual(v["policy.default_work_weekdays"], frozenset({5, 6, 0, 1, 2}))
        self.assertTrue(v["policy.allow_use_before_accrual"])
        self.assertEqual(v["policy.sick_proration"], "months")
        self.assertEqual(v["holidays.source"], "manual")

    def test_undecided_values_are_none_not_invented(self):
        v = S.defaults()
        self.assertIsNone(v["workflow.reminder_after_working_days"])
        self.assertIsNone(v["workflow.escalate_after_working_days"])

    def test_validation_rejects_bad_values(self):
        bad = [("policy.annual_days_per_month", "abc"), ("policy.annual_days_per_month", -1),
               ("policy.annual_days_per_month", "NaN"), ("policy.sick_days_per_year", 400),
               ("policy.leave_calendar", "hijri"), ("policy.weekly_off_weekdays", []),
               ("policy.weekly_off_weekdays", [7]), ("policy.weekly_off_weekdays", "4"),
               ("policy.weekly_off_weekdays", [True]), ("policy.allow_use_before_accrual", "yes"),
               ("workflow.escalate_after_working_days", 0), ("workflow.escalate_after_working_days", "3"),
               ("holidays.source", "api"), ("no.such.key", 1)]
        for k, v in bad:
            with self.assertRaises(S.SettingError, msg=f"{k}={v!r}"):
                S.validate_setting(k, v)

    def test_validation_accepts_and_normalizes(self):
        self.assertEqual(S.validate_setting("policy.annual_days_per_month", "2.5"), D("2.5"))
        self.assertEqual(S.validate_setting("policy.default_work_weekdays", [5, 6, 0, 1, 2, 3]),
                         frozenset({0, 1, 2, 3, 5, 6}))
        self.assertEqual(S.validate_setting("workflow.escalate_after_working_days", 3), 3)
        self.assertIsNone(S.validate_setting("workflow.escalate_after_working_days", None))

    def test_resolve_and_build_policy_applies_overrides(self):
        p = S.build_policy({"policy.leave_day_counting": COUNT_INCLUDE_WEEKLY_OFF_INSIDE,
                            "policy.sick_days_per_year": "12",
                            "policy.default_work_weekdays": [5, 6, 0, 1, 2, 3]})
        self.assertEqual(p.leave_day_counting, COUNT_INCLUDE_WEEKLY_OFF_INSIDE)
        self.assertEqual(p.sick_days_per_year, D(12))
        self.assertIn(3, p.default_work_weekdays)

    def test_corrupt_stored_value_raises_not_ignored(self):
        with self.assertRaises(S.SettingError):
            S.resolve({"policy.annual_days_per_month": "oops"})

    def test_to_storable_roundtrip(self):
        self.assertEqual(S.to_storable(D("2.5")), "2.5")
        self.assertEqual(S.to_storable(frozenset({4})), [4])
        self.assertEqual(S.validate_setting("policy.weekly_off_weekdays", S.to_storable(frozenset({3, 4}))),
                         frozenset({3, 4}))


class HolidayTests(unittest.TestCase):
    def test_no_hardcoded_holidays(self):
        self.assertEqual(H.holidays_in_range([], [], dt.date(2026, 1, 1), dt.date(2026, 12, 31)), set())

    def test_recurring_entry_resolves_each_year(self):
        e = H.make_entry("*", "تست سالانه", 1, 1)         # ۱ فروردین
        self.assertEqual(e.resolve(1405), dt.date(2026, 3, 21))
        self.assertEqual(e.resolve(1404), dt.date(2025, 3, 21))

    def test_one_off_entry_only_in_its_year(self):
        e = H.make_entry("*", "یک‌بار", 7, 10, 1405)
        self.assertIsNotNone(e.resolve(1405))
        self.assertIsNone(e.resolve(1406))

    def test_esfand_30_recurring_only_in_leap_years(self):
        e = H.make_entry("*", "۳۰ اسفند", 12, 30)
        self.assertIsNotNone(e.resolve(1403))
        self.assertIsNone(e.resolve(1404))

    def test_from_text_with_persian_digits(self):
        e = H.make_entry_from_text("*", "نمونه", "۱۴۰۵/۰۸/۰۶", recurring=False)
        self.assertEqual((e.jalali_year, e.jalali_month, e.jalali_day), (1405, 8, 6))
        r = H.make_entry_from_text("*", "نمونه", "۱۴۰۵/۰۸/۰۶", recurring=True)
        self.assertIsNone(r.jalali_year)
        with self.assertRaises(jalali.JalaliError):
            H.make_entry_from_text("*", "x", "1405/13/01", False)

    def test_validation(self):
        for args in [("*", "", 1, 1), ("", "x", 1, 1), ("*", "x", 13, 1), ("*", "x" * 201, 1, 1), ("*", "x", 1, 32)]:
            with self.assertRaises(H.HolidayError):
                H.make_entry(*args)
        with self.assertRaises(H.HolidayError):
            H.make_entry("*", "x", 12, 30, 1404)     # سال غیرکبیسه

    def test_scope_filtering_and_range(self):
        nat = H.make_entry("*", "ملی", 8, 6, 1405)
        comp = H.make_entry("CO-A", "شرکتی", 8, 7, 1405)
        other = H.make_entry("CO-B", "دیگر", 8, 8, 1405)
        s, e = dt.date(2026, 10, 1), dt.date(2026, 11, 30)
        got = H.holidays_in_range([nat, comp, other], ["CO-A"], s, e)
        self.assertEqual(got, {jalali.to_gregorian(1405, 8, 6), jalali.to_gregorian(1405, 8, 7)})

    def test_range_crossing_jalali_year_boundary(self):
        e = H.make_entry("*", "نوروز-نمونه", 1, 1)
        got = H.holidays_in_range([e], [], dt.date(2025, 3, 1), dt.date(2026, 4, 30))
        self.assertEqual(got, {dt.date(2025, 3, 21), dt.date(2026, 3, 21)})

    def test_duplicates_detected(self):
        a = H.make_entry("*", "الف", 8, 6, 1405)
        b = H.make_entry("*", "ب", 8, 6, None)       # سالانه روی همان روز
        with self.assertRaises(H.HolidayError):
            H.check_duplicates([a, b], [1405])
        H.check_duplicates([a, b], [1406])            # در ۱۴۰۶ فقط سالانه فعال است → بدون تکرار

    def test_diff_for_history(self):
        a = H.make_entry("*", "الف", 8, 6, 1405)
        b = H.make_entry("*", "ب", 8, 7, 1405)
        d = H.diff_entries([a], [a, b])
        self.assertEqual(d["added"], [b])
        self.assertEqual(d["removed"], [])

    def test_holiday_feeds_leave_counting(self):
        from zsh_core.policy import LeavePolicy, count_leave_days
        hol = H.make_entry("*", "نمونه", 8, 10, 1405)
        hset = H.holidays_in_range([hol], [], dt.date(2026, 11, 1), dt.date(2026, 11, 11))
        P = LeavePolicy()
        n = count_leave_days(dt.date(2026, 11, 1), dt.date(2026, 11, 11), P.default_work_weekdays, hset, P)
        base = count_leave_days(dt.date(2026, 11, 1), dt.date(2026, 11, 11), P.default_work_weekdays, [], P)
        wd = jalali.to_gregorian(1405, 8, 10).weekday()
        self.assertEqual(n, base - (1 if wd in P.default_work_weekdays else 0))


if __name__ == "__main__":
    unittest.main()
