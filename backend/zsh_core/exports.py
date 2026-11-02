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
    stripped = s.lstrip()
    if s.startswith(_DANGEROUS_PREFIX) or stripped.startswith(("=", "+", "-", "@")):
        return "'" + s
    return s


def iter_csv_bytes(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> Iterable[bytes]:
    """Yield UTF-8-BOM CSV output one row at a time."""
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\r\n")
    yield b"\xef\xbb\xbf"
    writer.writerow([sanitize_cell(header) for header in headers])
    yield buf.getvalue().encode("utf-8")
    for row in rows:
        buf.seek(0)
        buf.truncate(0)
        writer.writerow([sanitize_cell(cell) for cell in row])
        yield buf.getvalue().encode("utf-8")


def to_csv_bytes(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> bytes:
    """UTF-8 با BOM (برای نمایش صحیح فارسی در Excel) و پایان‌خط CRLF."""
    return b"".join(iter_csv_bytes(headers, rows))


def to_xlsx_bytes(headers: Sequence[str], rows: Iterable[Sequence[Any]], sheet_title: str = "گزارش") -> bytes:
    from openpyxl import Workbook
    wb = Workbook(write_only=True)
    wb.properties.creator = "ZSH Leave"
    wb.properties.lastModifiedBy = "ZSH Leave"
    wb.properties.title = "ZSH Leave export"
    wb.properties.subject = ""
    wb.properties.description = ""
    ws = wb.create_sheet(title=sheet_title[:31])
    ws.sheet_view.rightToLeft = True
    ws.append([sanitize_cell(h) for h in headers])
    for r in rows:
        ws.append([sanitize_cell(c) if not isinstance(c, Decimal) else float(c) for c in r])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
