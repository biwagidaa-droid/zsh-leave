import datetime as dt
import unittest
from decimal import Decimal as D
from zsh_core.balance import (Entitlement, RequestLine, compute_balance, allocate_by_year,
                              compute_carry_over, BalanceError)

d = dt.date


def line(status, s, e, wd, counts=True):
    return RequestLine(status, s, e, D(wd), counts)


class BalanceTests(unittest.TestCase):
    ENT = Entitlement(D("20"), D("3"), D("-1"))   # کل = 22

    def test_formula(self):
        b = compute_balance(self.ENT, [
            line("APPROVED", d(2026, 5, 3), d(2026, 5, 7), "5"),
            line("PENDING", d(2026, 6, 1), d(2026, 6, 2), "2"),
            line("ESCALATED", d(2026, 7, 1), d(2026, 7, 1), "1"),
        ], 2026)
        self.assertEqual((b.total, b.used, b.pending), (D(22), D(5), D(3)))
        self.assertEqual(b.remaining, D(17))
        self.assertEqual(b.available, D(14))

    def test_rejected_and_cancelled_have_no_effect(self):
        b = compute_balance(self.ENT, [line("REJECTED", d(2026, 5, 3), d(2026, 5, 7), "5"),
                                       line("CANCELLED", d(2026, 5, 3), d(2026, 5, 7), "5")], 2026)
        self.assertEqual((b.used, b.pending), (D(0), D(0)))

    def test_withdrawal_pending_stays_used_not_double_counted(self):  # فرض C-3
        b = compute_balance(self.ENT, [line("WITHDRAWAL_PENDING", d(2026, 5, 3), d(2026, 5, 7), "5")], 2026)
        self.assertEqual((b.used, b.pending), (D(5), D(0)))

    def test_non_counting_type_ignored(self):
        b = compute_balance(self.ENT, [line("APPROVED", d(2026, 5, 3), d(2026, 5, 7), "5", counts=False)], 2026)
        self.assertEqual(b.used, D(0))

    def test_missing_entitlement_raises_no_fake_balance(self):
        with self.assertRaises(BalanceError):
            compute_balance(None, [], 2026)

    def test_negative_available_is_allowed_not_blocked(self):
        b = compute_balance(Entitlement(D("2")), [line("APPROVED", d(2026, 5, 3), d(2026, 5, 7), "5")], 2026)
        self.assertEqual(b.remaining, D(-3))

    def test_year_split_sums_to_total(self):
        ln = line("APPROVED", d(2026, 12, 28), d(2027, 1, 3), "5")
        a = allocate_by_year(ln)
        self.assertEqual(sum(a.values()), D(5))
        self.assertEqual(set(a), {2026, 2027})
        b26 = compute_balance(self.ENT, [ln], 2026)
        b27 = compute_balance(self.ENT, [ln], 2027)
        self.assertEqual(b26.used + b27.used, D(5))

    def test_year_split_uses_workday_weights(self):
        # فقط روزهای ۲۸ تا ۳۰ دسامبر کاری‌اند → کل سهم به ۲۰۲۶
        wd = lambda x: x.year == 2026 and x.day in (28, 29, 30)
        a = allocate_by_year(line("APPROVED", d(2026, 12, 28), d(2027, 1, 3), "3"), wd)
        self.assertEqual(a, {2026: D(3)})

    def test_invalid_lines(self):
        with self.assertRaises(BalanceError):
            allocate_by_year(line("APPROVED", d(2026, 5, 7), d(2026, 5, 3), "1"))
        with self.assertRaises(BalanceError):
            allocate_by_year(line("APPROVED", d(2026, 5, 3), d(2026, 5, 7), "0"))

    def test_carry_over_policies(self):
        self.assertEqual(compute_carry_over(D("8"), "none"), D(0))
        self.assertEqual(compute_carry_over(D("8"), "unlimited"), D(8))
        self.assertEqual(compute_carry_over(D("8"), "capped", D("5")), D(5))
        self.assertEqual(compute_carry_over(D("3"), "capped", D("5")), D(3))
        self.assertEqual(compute_carry_over(D("-2"), "unlimited"), D(0))
        with self.assertRaises(BalanceError):
            compute_carry_over(D("3"), "capped")
        with self.assertRaises(BalanceError):
            compute_carry_over(D("3"), "weird")


if __name__ == "__main__":
    unittest.main()
