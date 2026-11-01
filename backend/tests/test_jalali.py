import datetime as dt
import unittest
from zsh_core import jalali as j


class JalaliTests(unittest.TestCase):
    # نوروز رسمی (مرجع: تقویم رسمی ایران)
    NOWRUZ = {1399: (2020, 3, 20), 1400: (2021, 3, 21), 1401: (2022, 3, 21),
              1402: (2023, 3, 21), 1403: (2024, 3, 20), 1404: (2025, 3, 21),
              1405: (2026, 3, 21)}

    def test_nowruz_dates(self):
        for jy, (y, m, d) in self.NOWRUZ.items():
            self.assertEqual(j.to_gregorian(jy, 1, 1), dt.date(y, m, d), jy)
            self.assertEqual(j.from_gregorian(dt.date(y, m, d)), (jy, 1, 1), jy)

    def test_leap_years_known(self):
        for y in (1399, 1403, 1408, 1395, 1391, 1387):
            self.assertTrue(j.is_leap(y), y)
        for y in (1400, 1401, 1402, 1404, 1405):
            self.assertFalse(j.is_leap(y), y)

    def test_esfand_30_in_leap_year(self):
        self.assertEqual(j.to_gregorian(1403, 12, 30), dt.date(2025, 3, 20))
        with self.assertRaises(j.JalaliError):
            j.to_gregorian(1404, 12, 30)

    def test_year_boundary_no_off_by_one(self):
        self.assertEqual(j.from_gregorian(dt.date(2025, 3, 20)), (1403, 12, 30))
        self.assertEqual(j.from_gregorian(dt.date(2025, 3, 21)), (1404, 1, 1))
        self.assertEqual(j.from_gregorian(dt.date(2024, 3, 19)), (1402, 12, 29))

    def test_known_mid_dates(self):
        self.assertEqual(j.to_gregorian(1403, 11, 22), dt.date(2025, 2, 10))   # ۲۲ بهمن
        self.assertEqual(j.from_gregorian(dt.date(2026, 10, 28)), (1405, 8, 6))  # ۶ آبان ۱۴۰۵

    def test_roundtrip_every_day_full_range(self):
        d = j.to_gregorian(1343, 1, 1)
        end = j.to_gregorian(1472, 12, j.month_length(1472, 12))
        prev = None
        while d <= end:
            y, m, dd = j.from_gregorian(d)
            self.assertEqual(j.to_gregorian(y, m, dd), d)
            cur = (y, m, dd)
            if prev:  # پیوستگی: روز بعد یا اول ماه بعد
                self.assertTrue(cur > prev)
            prev = cur
            d += dt.timedelta(days=1)

    def test_out_of_range_raises(self):
        with self.assertRaises(j.JalaliError):
            j.to_gregorian(1300, 1, 1)
        with self.assertRaises(j.JalaliError):
            j.from_gregorian(dt.date(2200, 1, 1))

    def test_parse_and_format_persian_digits(self):
        self.assertEqual(j.parse_jalali("۱۴۰۴/۰۱/۰۱"), dt.date(2025, 3, 21))
        self.assertEqual(j.format_jalali(dt.date(2025, 3, 21)), "1404/01/01")
        self.assertEqual(j.format_jalali(dt.date(2025, 3, 21), True), "1 فروردین 1404")
        with self.assertRaises(j.JalaliError):
            j.parse_jalali("1404/13/01")
        with self.assertRaises(j.JalaliError):
            j.parse_jalali("abc")


if __name__ == "__main__":
    unittest.main()
