"""ورود گروهی سهمیه از CSV با اعتبارسنجی کامل و Dry Run. این ماژول فقط تحلیل می‌کند؛ ذخیره در لایه سرویس
و فقط اگر گزارش بدون خطا باشد (همه‌یاهیچ) انجام می‌شود."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Mapping

REQUIRED = ("personnel_code", "leave_type_key", "year", "base_days")
MAX_ROWS = 5000
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")
_YEAR_PATTERN = re.compile(r"[0-9]{1,4}\Z")
_DAYS_PATTERN = re.compile(r"[0-9]+(?:\.[0-9])?\Z")


@dataclass(frozen=True)
class ImportIssue:
    line: int
    code: str
    message: str


@dataclass(frozen=True)
class ValidRow:
    line: int
    personnel_code: str
    employee_id: int
    leave_type_key: str
    year: int
    base_days: Decimal


@dataclass
class ImportReport:
    valid: list[ValidRow] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)    # (شماره خط، پیام فارسی)
    issues: list[ImportIssue] = field(default_factory=list)
    fatal: str | None = None
    fatal_code: str | None = None

    @property
    def ok(self) -> bool:
        return self.fatal is None and not self.issues and bool(self.valid)


def parse_entitlement_csv(data: bytes | str, employees_by_code: Mapping[str, int],
                          known_type_keys: set[str], year_min: int, year_max: int, *,
                          header_aliases: Mapping[str, str] | None = None,
                          minimum_days: Decimal = Decimal("0"),
                          maximum_days: Decimal = Decimal("366")) -> ImportReport:
    rep = ImportReport()
    try:
        if isinstance(data, bytes):
            text = data.decode("utf-8-sig")
        elif isinstance(data, str):
            text = data.lstrip("\ufeff")
        else:
            rep.fatal_code = "invalid_input"
            rep.fatal = "محتوای CSV باید متن UTF-8 باشد"
            return rep
    except UnicodeDecodeError:
        rep.fatal_code = "invalid_encoding"
        rep.fatal = "کدگذاری فایل باید UTF-8 باشد"
        return rep

    try:
        reader = csv.DictReader(
            io.StringIO(text, newline=""),
            restkey="__extra_columns__",
            strict=True,
        )
        raw_headers = reader.fieldnames or []
        if not raw_headers:
            rep.fatal_code = "empty_file"
            rep.fatal = "فایل CSV خالی است یا سرستون ندارد"
            return rep
        aliases = header_aliases or {}
        headers = [aliases.get((header or "").strip(), (header or "").strip())
                   for header in raw_headers]
        if any(not header for header in headers):
            rep.fatal_code = "invalid_header"
            rep.fatal = "نام سرستون نمی‌تواند خالی باشد"
            return rep
        if len(set(headers)) != len(headers):
            rep.fatal_code = "duplicate_header"
            rep.fatal = "سرستون تکراری در فایل وجود دارد"
            return rep
        missing = [h for h in REQUIRED if h not in headers]
        if missing:
            rep.fatal_code = "missing_header"
            rep.fatal = "ستون‌های الزامی وجود ندارد: " + "، ".join(missing)
            return rep
        extra_headers = [header for header in headers if header not in REQUIRED]
        if extra_headers:
            rep.fatal_code = "extra_header"
            rep.fatal = "ستون‌های اضافی پشتیبانی نمی‌شوند: " + "، ".join(extra_headers)
            return rep
        reader.fieldnames = headers
        seen: dict[tuple[int, str, int], int] = {}
        for i, raw in enumerate(reader, start=2):               # خط ۱ = سرستون
            if i - 1 > MAX_ROWS:
                rep.fatal_code = "too_many_rows"
                rep.fatal = f"تعداد ردیف‌ها بیش از {MAX_ROWS} است"
                return rep
            row = {
                key: value.strip() if isinstance(value, str) else value
                for key, value in raw.items()
                if key is not None and key != "__extra_columns__"
            }
            if all(value is None or value == "" for value in row.values()):
                continue
            line = reader.line_num
            if (
                raw.get("__extra_columns__") is not None
                or any(value is None for value in row.values())
            ):
                _row_error(rep, line, "invalid_column_count", "تعداد ستون‌های ردیف با سرستون‌ها برابر نیست")
                continue
            code, tkey = row.get("personnel_code", ""), row.get("leave_type_key", "")
            emp_id = employees_by_code.get(code)
            if not code or emp_id is None:
                _row_error(rep, line, "invalid_employee", "کارمند در محدوده مجاز پیدا نشد")
                continue
            if tkey not in known_type_keys:
                _row_error(rep, line, "invalid_leave_type", "نوع مرخصی نامعتبر یا غیرفعال است")
                continue
            year_text = row.get("year")
            normalized_year = year_text.translate(_DIGITS) if isinstance(year_text, str) else ""
            if not _YEAR_PATTERN.fullmatch(normalized_year):
                _row_error(rep, line, "invalid_year", "سال باید عدد صحیح یک تا چهار رقمی باشد")
                continue
            year = int(normalized_year)
            if not year_min <= year <= year_max:
                _row_error(
                    rep, line, "year_out_of_range",
                    f"سال باید بین {year_min} و {year_max} باشد",
                )
                continue
            days_text = row.get("base_days")
            normalized_days = days_text.translate(_DIGITS) if isinstance(days_text, str) else ""
            if not _DAYS_PATTERN.fullmatch(normalized_days):
                _row_error(rep, line, "invalid_days", "مقدار روز باید عدد مثبت با حداکثر یک رقم اعشار باشد")
                continue
            try:
                days = Decimal(normalized_days)
            except InvalidOperation:
                _row_error(rep, line, "invalid_days", "مقدار روز معتبر نیست")
                continue
            if not days.is_finite() or not minimum_days <= days <= maximum_days:
                _row_error(
                    rep, line, "invalid_days",
                    f"مقدار روز باید بین {minimum_days} و {maximum_days} باشد",
                )
                continue
            key = (emp_id, tkey, year)
            if key in seen:
                _row_error(
                    rep, line, "duplicate_in_file",
                    f"رکورد تکراری (مشابه خط {seen[key]})",
                )
                continue
            seen[key] = line
            rep.valid.append(ValidRow(line, code, emp_id, tkey, year, days))
        if not rep.valid and not rep.issues:
            rep.fatal_code = "empty_file"
            rep.fatal = "فایل ردیف داده‌ای ندارد"
    except csv.Error as e:
        rep.fatal_code = "malformed_csv"
        rep.fatal = f"فایل CSV معتبر نیست: {e}"
    return rep


def _row_error(report: ImportReport, line: int, code: str, message: str) -> None:
    report.issues.append(ImportIssue(line, code, message))
    report.errors.append((line, message))
