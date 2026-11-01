from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q

from zsh_core.imports import MAX_ROWS, ImportIssue, ValidRow, parse_entitlement_csv
from .authorization import hr_operation_employees
from .models import EmployeeProfile, LeaveEntitlement, LeaveType

MIN_IMPORT_YEAR = 1
MAX_IMPORT_YEAR = 9999
IMPORT_HEADER_ALIASES = {"type": "leave_type_key", "days": "base_days"}


@dataclass(frozen=True)
class EntitlementImportValidation:
    preview: dict
    valid_rows: tuple[tuple[int, EmployeeProfile, LeaveType, int, Decimal], ...]


def validate_entitlement_import(csv_data: bytes | str, context) -> EntitlementImportValidation:
    """Validate an entire import against scoped references, file duplicates, and stored keys."""
    scoped_employees = list(
        hr_operation_employees(context).order_by("pk").values("pk", "personnel_code")
    )
    employees_by_code: dict[str, int] = {}
    ambiguous_codes: set[str] = set()
    for employee in scoped_employees:
        code = employee["personnel_code"]
        if code in employees_by_code:
            ambiguous_codes.add(code)
        else:
            employees_by_code[code] = employee["pk"]
    for code in ambiguous_codes:
        employees_by_code.pop(code, None)

    leave_types = {
        leave_type.key: leave_type
        for leave_type in LeaveType.objects.filter(enabled=True).order_by("pk")
    }
    report = parse_entitlement_csv(
        csv_data,
        employees_by_code,
        set(leave_types),
        MIN_IMPORT_YEAR,
        MAX_IMPORT_YEAR,
        header_aliases=IMPORT_HEADER_ALIASES,
        minimum_days=Decimal("0.1"),
        maximum_days=Decimal("366"),
    )

    existing_keys = _existing_entitlement_keys(report.valid)
    if existing_keys:
        retained: list[ValidRow] = []
        for row in report.valid:
            key = (row.employee_id, row.leave_type_key, row.year)
            if key in existing_keys:
                report.issues.append(ImportIssue(
                    row.line,
                    "duplicate_existing",
                    "سهمیه این کارمند، نوع مرخصی و سال از قبل ثبت شده است",
                ))
                report.errors.append((
                    row.line,
                    "سهمیه این کارمند، نوع مرخصی و سال از قبل ثبت شده است",
                ))
            else:
                retained.append(row)
        report.valid = retained

    employee_ids = {row.employee_id for row in report.valid}
    employee_objects = {
        employee.pk: employee
        for employee in hr_operation_employees(context).filter(
            pk__in=employee_ids,
        ).select_related("user", "company")
    }
    valid_rows = tuple(
        (
            row.line,
            employee_objects[row.employee_id],
            leave_types[row.leave_type_key],
            row.year,
            row.base_days,
        )
        for row in report.valid
        if row.employee_id in employee_objects
    )
    if len(valid_rows) != len(report.valid):
        valid_row_lines = {row[0] for row in valid_rows}
        for row in report.valid:
            if row.line not in valid_row_lines:
                _append_issue(report, ImportIssue(
                    row.line,
                    "invalid_employee",
                    "کارمند در محدوده مجاز پیدا نشد",
                ))
        report.valid = [row for row in report.valid if row.line in valid_row_lines]

    rows_by_line: dict[int, dict] = {}
    for line, employee, leave_type, year, days in valid_rows:
        rows_by_line[line] = {
            "line": line,
            "employee": employee.personnel_code,
            "type": leave_type.key,
            "year": year,
            "days": str(days),
            "ok": True,
        }
    for issue in report.issues:
        row = rows_by_line.get(issue.line, {
            "line": issue.line,
            "employee": "",
            "type": "",
            "year": 0,
            "days": "",
            "ok": False,
        })
        row.update(ok=False, errorCode=issue.code, error=issue.message)
        rows_by_line[issue.line] = row
    fatal_count = 0
    if report.fatal is not None:
        fatal_count = 1
        fatal_line = MAX_ROWS + 2 if report.fatal_code == "too_many_rows" else 1
        rows_by_line[fatal_line] = {
            "line": fatal_line,
            "employee": "",
            "type": "",
            "year": 0,
            "days": "",
            "ok": False,
            "errorCode": report.fatal_code or "invalid_file",
            "error": report.fatal,
        }

    preview = {
        "dryRun": True,
        "rows": [rows_by_line[line] for line in sorted(rows_by_line)],
        "accepted": len(valid_rows),
        "rejected": len(report.issues) + fatal_count,
    }
    return EntitlementImportValidation(preview, valid_rows)


def _existing_entitlement_keys(rows: list[ValidRow]) -> set[tuple[int, str, int]]:
    keys = list(dict.fromkeys(
        (row.employee_id, row.leave_type_key, row.year)
        for row in rows
    ))
    existing: set[tuple[int, str, int]] = set()
    for offset in range(0, len(keys), 200):
        query = Q()
        for employee_id, leave_type_key, year in keys[offset:offset + 200]:
            query |= Q(
                employee_id=employee_id,
                leave_type__key=leave_type_key,
                year=year,
            )
        existing.update(
            LeaveEntitlement.objects.filter(query).values_list(
                "employee_id", "leave_type__key", "year",
            )
        )
    return existing


def _append_issue(report, issue: ImportIssue) -> None:
    report.issues.append(issue)
    report.errors.append((issue.line, issue.message))
