"""ورود گروهی سهمیه از CSV با اعتبارسنجی کامل و Dry Run. این ماژول فقط تحلیل می‌کند؛ ذخیره در لایه سرویس
و فقط اگر گزارش بدون خطا باشد (همه‌یاهیچ) انجام می‌شود."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Mapping

REQUIRED = ("personnel_code", "leave_type_key", "year", "base_days")
MAX_ROWS = 5000
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")


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
    fatal: str | None = None

    @property
    def ok(self) -> bool:
        return self.fatal is None and not self.errors and bool(self.valid)


def parse_entitlement_csv(data: bytes | str, employees_by_code: Mapping[str, int],
                          known_type_keys: set[str], year_min: int, year_max: int) -> ImportReport:
    rep = ImportReport()
    text = data.decode("utf-8-sig") if isinstance(data, bytes) else data.lstrip("\ufeff")
    try:
        reader = csv.DictReader(io.StringIO(text))
        headers = [h.strip() for h in (reader.fieldnames or [])]
        missing = [h for h in REQUIRED if h not in headers]
        if missing:
            rep.fatal = "ستون‌های الزامی وجود ندارد: " + "، ".join(missing)
            return rep
        seen: dict[tuple, int] = {}
        for i, raw in enumerate(reader, start=2):               # خط ۱ = سرستون
            if i - 1 > MAX_ROWS:
                rep.fatal = f"تعداد ردیف‌ها بیش از {MAX_ROWS} است"
                return rep
            row = {(k or "").strip(): (v or "").strip() for k, v in raw.items() if k is not None}
            if not any(row.values()):
                continue
            code, tkey = row.get("personnel_code", ""), row.get("leave_type_key", "")
            err = None
            emp_id = employees_by_code.get(code)
            if not code or emp_id is None:
                err = "کد پرسنلی ناشناخته یا خالی است"
            elif tkey not in known_type_keys:
                err = "نوع مرخصی ناشناخته است"
            year = days = None
            if err is None:
                try:
                    year = int(row["year"].translate(_DIGITS))
                    if not year_min <= year <= year_max:
                        err = f"سال باید بین {year_min} و {year_max} باشد"
                except ValueError:
                    err = "سال نامعتبر است"
            if err is None:
                try:
                    days = Decimal(row["base_days"].translate(_DIGITS))
                    if not days.is_finite() or days < 0 or days > 366 or days != days.quantize(Decimal("0.1")):
                        err = "مقدار روز باید بین ۰ و ۳۶۶ با حداکثر یک رقم اعشار باشد"
                except InvalidOperation:
                    err = "مقدار روز نامعتبر است"
            if err is None:
                key = (emp_id, tkey, year)
                if key in seen:
                    err = f"رکورد تکراری (مشابه خط {seen[key]})"
                else:
                    seen[key] = i
            if err:
                rep.errors.append((i, err))
            else:
                rep.valid.append(ValidRow(i, code, emp_id, tkey, year, days))
    except csv.Error as e:
        rep.fatal = f"فایل CSV معتبر نیست: {e}"
    return rep
