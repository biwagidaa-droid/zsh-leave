"""خروجی CSV/XLSX امن: جلوگیری از Formula Injection و نمایش درست فارسی در Excel."""
from __future__ import annotations

import csv
import io
from decimal import Decimal
from typing import Any, Iterable, Sequence

_DANGEROUS_PREFIX = ("=", "+", "-", "@", "\t", "\r", "\n")


def sanitize_cell(v: Any) -> Any:
    """رشته‌های شروع‌شونده با نویسه‌های فرمول با ' خنثی می‌شوند. عددها (int/Decimal/float) دست‌نخورده‌اند."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "بله" if v else "خیر"
    if isinstance(v, (int, float, Decimal)):
        return v
    s = str(v)
    stripped = s.lstrip(" ")
    if stripped.startswith(_DANGEROUS_PREFIX):
        return "'" + s
    return s


def to_csv_bytes(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    """UTF-8 با BOM (برای نمایش صحیح فارسی در Excel) و پایان‌خط CRLF."""
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow([sanitize_cell(h) for h in headers])
    for r in rows:
        w.writerow([sanitize_cell(c) for c in r])
    return buf.getvalue().encode("utf-8-sig")


def to_xlsx_bytes(headers: Sequence[str], rows: Iterable[Sequence[Any]], sheet_title: str = "گزارش") -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    ws.sheet_view.rightToLeft = True
    ws.append([sanitize_cell(h) for h in headers])
    for r in rows:
        ws.append([sanitize_cell(c) if not isinstance(c, Decimal) else float(c) for c in r])
    # رشته‌ها همیشه به‌صورت متن ذخیره شوند تا Excel آن‌ها را فرمول تفسیر نکند
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
