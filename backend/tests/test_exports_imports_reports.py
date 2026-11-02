import datetime as dt
import io
import unittest
from decimal import Decimal as D
from zsh_core import exports as X, imports as I, reports as R

d = dt.date


class ExportTests(unittest.TestCase):
    def test_formula_injection_neutralized(self):
        for bad in ("=SUM(A1)", "+1+1", "-2+3", "@cmd", "\t=1", "  =HYPERLINK(\"x\")", "\r=1"):
            self.assertTrue(str(X.sanitize_cell(bad)).startswith("'"), bad)
        for ok in ("سلام", "علی=رضا", "۱۴۰۵/۰۱/۰۱", "x"):
            self.assertEqual(X.sanitize_cell(ok), ok)

    def test_numbers_untouched_negative_numbers_ok(self):
        self.assertEqual(X.sanitize_cell(D("-1.5")), D("-1.5"))
        self.assertEqual(X.sanitize_cell(-3), -3)
        self.assertEqual(X.sanitize_cell(None), "")

    def test_csv_bom_and_persian(self):
        b = X.to_csv_bytes(["نام", "روز"], [["=EVIL()", D("2.5")], ["علی", 3]])
        self.assertTrue(b.startswith(b"\xef\xbb\xbf"))
        txt = b.decode("utf-8-sig")
        self.assertIn("نام,روز\r\n", txt)
        self.assertIn("'=EVIL(),2.5", txt)
        self.assertIn("علی,3", txt)

    def test_xlsx_roundtrip_no_formula(self):
        from openpyxl import load_workbook
        b = X.to_xlsx_bytes(["نام", "مقدار"], [["=1+1", D("2.5")], ["علی", 4]])
        ws = load_workbook(io.BytesIO(b)).active
        self.assertEqual(ws["A2"].value, "'=1+1")
        self.assertNotEqual(ws["A2"].data_type, "f")
        self.assertEqual(ws["A3"].value, "علی")
        self.assertEqual(ws["B2"].value, 2.5)
        self.assertTrue(ws.sheet_view.rightToLeft)


EMP = {"P001": 1, "P002": 2}
TYPES = {"annual", "sick"}


def parse(text):
    return I.parse_entitlement_csv(text, EMP, TYPES, 1400, 1410)


class ImportTests(unittest.TestCase):
    HEAD = "personnel_code,leave_type_key,year,base_days\n"

    def test_valid_file(self):
        r = parse(self.HEAD + "P001,annual,1405,30\nP002,sick,۱۴۰۵,۱۰\n")
        self.assertTrue(r.ok, r.errors)
        self.assertEqual([(v.employee_id, v.year, v.base_days) for v in r.valid], [(1, 1405, D(30)), (2, 1405, D(10))])

    def test_bom_and_blank_lines(self):
        r = parse("\ufeff" + self.HEAD + "\nP001,annual,1405,30\n,,,\n")
        self.assertTrue(r.ok)
        self.assertEqual(len(r.valid), 1)

    def test_missing_columns_fatal(self):
        r = parse("personnel_code,year\nP001,1405\n")
        self.assertIsNotNone(r.fatal)
        self.assertFalse(r.ok)

    def test_row_errors_reported_with_line_numbers(self):
        r = parse(self.HEAD + "PXXX,annual,1405,30\nP001,weird,1405,30\nP001,annual,1300,30\n"
                              "P001,annual,1405,-1\nP001,annual,1405,2.55\nP001,annual,1405,abc\nP001,annual,xx,3\n")
        self.assertEqual([ln for ln, _ in r.errors], [2, 3, 4, 5, 6, 7, 8])
        self.assertFalse(r.ok)
        self.assertEqual(r.valid, [])

    def test_duplicates_detected(self):
        r = parse(self.HEAD + "P001,annual,1405,30\nP001,annual,1405,25\n")
        self.assertEqual(len(r.errors), 1)
        self.assertIn("تکراری", r.errors[0][1])
        self.assertFalse(r.ok)

    def test_partial_validity_is_not_ok(self):   # همه‌یاهیچ: ذخیره فقط اگر ok
        r = parse(self.HEAD + "P001,annual,1405,30\nPXXX,annual,1405,30\n")
        self.assertEqual(len(r.valid), 1)
        self.assertFalse(r.ok)

    def test_row_limit(self):
        body = "".join("P001,annual,1405,1\n" for _ in range(I.MAX_ROWS + 1))
        self.assertIsNotNone(parse(self.HEAD + body).fatal)

    def test_empty_file_not_ok(self):
        self.assertFalse(parse(self.HEAD).ok)

    def test_invalid_utf8_and_short_rows_are_rejected(self):
        invalid_encoding = I.parse_entitlement_csv(
            b"\xff", EMP, TYPES, 1400, 1410,
        )
        self.assertEqual(invalid_encoding.fatal_code, "invalid_encoding")

        short_row = parse(self.HEAD + "P001,annual,1405\n")
        self.assertEqual(short_row.issues[0].code, "invalid_column_count")
        self.assertEqual(short_row.issues[0].line, 2)

    def test_duplicate_headers_extra_cells_and_malformed_csv_are_rejected(self):
        duplicate_headers = I.parse_entitlement_csv(
            "personnel_code,type,leave_type_key,year,days\n",
            EMP,
            TYPES,
            1400,
            1410,
            header_aliases={"type": "leave_type_key", "days": "base_days"},
        )
        self.assertEqual(duplicate_headers.fatal_code, "duplicate_header")

        extra_cell = parse(self.HEAD + "P001,annual,1405,10,extra\n")
        self.assertEqual(extra_cell.issues[0].code, "invalid_column_count")

        malformed = parse(self.HEAD + 'P001,"annual,1405,10\n')
        self.assertEqual(malformed.fatal_code, "malformed_csv")


class ReportTests(unittest.TestCase):
    W = (d(2026, 3, 21), d(2027, 3, 20))

    def test_bradford_basic(self):
        r = R.bradford_factor([(d(2026, 5, 1), d(2026, 5, 3)), (d(2026, 8, 1), d(2026, 8, 1)),
                               (d(2026, 9, 1), d(2026, 9, 2))], *self.W)
        self.assertEqual((r["spells"], r["days"], r["score"]), (3, 6, 54))

    def test_bradford_merges_adjacent_and_overlapping(self):
        r = R.bradford_factor([(d(2026, 5, 1), d(2026, 5, 3)), (d(2026, 5, 4), d(2026, 5, 4)),
                               (d(2026, 5, 3), d(2026, 5, 6))], *self.W)
        self.assertEqual((r["spells"], r["days"], r["score"]), (1, 6, 6))

    def test_bradford_clips_to_window_and_ignores_outside(self):
        r = R.bradford_factor([(d(2026, 3, 18), d(2026, 3, 22)), (d(2025, 1, 1), d(2025, 1, 5))], *self.W)
        self.assertEqual((r["spells"], r["days"]), (1, 2))
        self.assertIn("مبنای تصمیم", r["note"])

    def test_bradford_bad_window(self):
        with self.assertRaises(ValueError):
            R.bradford_factor([], d(2027, 1, 1), d(2026, 1, 1))

    def test_decision_stats(self):
        self.assertEqual(R.decision_time_stats([1, 2, 3, 10]), {"count": 4, "mean": 4.0, "median": 2.5})
        self.assertEqual(R.decision_time_stats([]), {"count": 0, "mean": None, "median": None})

    def test_small_group_suppression(self):
        self.assertEqual(R.suppress_small_groups({"A": 10, "B": 2, "C": 0}, 5), {"A": 10, "B": None, "C": 0})
        with self.assertRaises(ValueError):
            R.suppress_small_groups({}, 1)

    def test_secondary_suppression_hides_total(self):
        out, total = R.suppress_with_total({"A": 10, "B": 2, "C": 8}, 5)
        self.assertIsNone(out["B"])
        self.assertIsNone(out["C"])            # سرکوب ثانویه: کوچک‌ترین گروه باقی‌مانده
        self.assertIsNone(total)
        out2, total2 = R.suppress_with_total({"A": 10, "B": 6}, 5)
        self.assertEqual((out2, total2), ({"A": 10, "B": 6}, 16))


if __name__ == "__main__":
    unittest.main()
