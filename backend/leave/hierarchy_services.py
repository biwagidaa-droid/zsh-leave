from __future__ import annotations

from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Company, Department, EmployeeProfile

MAX_HIERARCHY_DEPTH = 1000


def lock_organizational_hierarchy() -> None:
    """Serialize hierarchy writes across companies in a stable lock order."""
    list(Company.objects.select_for_update().order_by("pk").values_list("pk", flat=True))


def _validate_department_parent(department: Department) -> None:
    if department.parent_id is None:
        return
    if department.pk is not None and department.parent_id == department.pk:
        raise ValidationError({"parent": "یک واحد نمی‌تواند والد خودش باشد"})

    parent_data = Department.objects.filter(pk=department.parent_id).values(
        "company_id", "parent_id",
    ).first()
    if parent_data is None:
        raise ValidationError({"parent": "واحد والد پیدا نشد"})
    if parent_data["company_id"] != department.company_id:
        raise ValidationError({"parent": "واحد والد باید متعلق به همان شرکت باشد"})

    visited: set[int] = set()
    current_id = department.parent_id
    for _ in range(MAX_HIERARCHY_DEPTH):
        if current_id is None:
            return
        if current_id == department.pk or current_id in visited:
            raise ValidationError({"parent": "تغییر والد باعث ایجاد چرخه در ساختار واحدها می‌شود"})
        visited.add(current_id)
        node = Department.objects.filter(pk=current_id).values(
            "company_id", "parent_id",
        ).first()
        if node is None:
            raise ValidationError({"parent": "زنجیره والد واحد معتبر نیست"})
        if node["company_id"] != department.company_id:
            raise ValidationError({"parent": "همه والدهای واحد باید متعلق به همان شرکت باشند"})
        current_id = node["parent_id"]
    raise ValidationError({"parent": "عمق ساختار واحدها از حد مجاز بیشتر است"})


def _is_active_manager(employee: EmployeeProfile, today) -> bool:
    return (
        employee.is_employee
        and employee.account_status == EmployeeProfile.ACCOUNT_ACTIVATED
        and employee.user.is_active
        and employee.start_date <= today
        and (employee.end_date is None or employee.end_date >= today)
    )


def _validate_manager_chain(employee: EmployeeProfile) -> None:
    if employee.manager_id is None:
        return
    if employee.pk is not None and employee.manager_id == employee.pk:
        raise ValidationError({"manager": "کارمند نمی‌تواند مدیر خودش باشد"})

    today = timezone.localdate()
    visited: set[int] = set()
    current_id = employee.manager_id
    for _ in range(MAX_HIERARCHY_DEPTH):
        if current_id is None:
            return
        if current_id == employee.pk or current_id in visited:
            raise ValidationError({"manager": "تغییر مدیر باعث ایجاد چرخه گزارش‌دهی می‌شود"})
        visited.add(current_id)
        manager = EmployeeProfile.objects.select_related("user").filter(pk=current_id).first()
        if manager is None:
            raise ValidationError({"manager": "مدیر پیدا نشد"})
        if manager.company_id != employee.company_id:
            raise ValidationError({"manager": "مدیر باید متعلق به همان شرکت باشد"})
        if not _is_active_manager(manager, today):
            raise ValidationError({"manager": "مدیر باید کارمند فعال با حساب فعال باشد"})
        current_id = manager.manager_id
    raise ValidationError({"manager": "عمق زنجیره مدیران از حد مجاز بیشتر است"})


def validate_department_relationships(department: Department) -> None:
    if department.company_id is None:
        return
    _validate_department_parent(department)
    if department.pk is not None:
        original_company_id = Department.objects.filter(pk=department.pk).values_list(
            "company_id", flat=True,
        ).first()
        if original_company_id is not None and original_company_id != department.company_id:
            if Department.objects.filter(parent_id=department.pk).exists():
                raise ValidationError({"company": "واحد دارای زیرواحد را نمی‌توان به شرکت دیگری منتقل کرد"})
            if EmployeeProfile.objects.filter(department_id=department.pk).exists():
                raise ValidationError({"company": "واحد دارای کارمند را نمی‌توان به شرکت دیگری منتقل کرد"})


def validate_employee_relationships(employee: EmployeeProfile) -> None:
    if employee.company_id is None:
        return
    if employee.department_id and not Department.objects.filter(
        pk=employee.department_id, company_id=employee.company_id,
    ).exists():
        raise ValidationError({"department": "واحد باید متعلق به همان شرکت باشد"})
    _validate_manager_chain(employee)
    if employee.pk is not None:
        original_company_id = EmployeeProfile.objects.filter(pk=employee.pk).values_list(
            "company_id", flat=True,
        ).first()
        if original_company_id is not None and original_company_id != employee.company_id:
            if EmployeeProfile.objects.filter(manager_id=employee.pk).exists():
                raise ValidationError({"company": "کارمندی که مدیر مستقیم دارد را نمی‌توان به شرکت دیگری منتقل کرد"})
        if EmployeeProfile.objects.filter(manager_id=employee.pk).exists() and not _is_active_manager(
            employee, timezone.localdate(),
        ):
            raise ValidationError({"account_status": "مدیر دارای گزارش مستقیم باید کارمند فعال باقی بماند"})


def hierarchy_issues() -> list[dict]:
    """Return relationship violations without following corrupt graphs recursively."""
    departments = list(Department.objects.order_by("pk").values(
        "id", "company_id", "parent_id",
    ))
    employees = list(EmployeeProfile.objects.order_by("pk").values(
        "id", "company_id", "department_id", "manager_id", "is_employee", "user__is_active",
        "account_status", "start_date", "end_date",
    ))
    today = timezone.localdate()
    issues: list[dict] = []
    department_by_id = {row["id"]: row for row in departments}
    employee_by_id = {row["id"]: row for row in employees}

    for row in departments:
        parent_id = row["parent_id"]
        if parent_id is None:
            continue
        parent = department_by_id.get(parent_id)
        reason = None
        if parent_id == row["id"]:
            reason = "self_parent"
        elif parent is None:
            reason = "missing_parent"
        elif parent["company_id"] != row["company_id"]:
            reason = "cross_company_parent"
        if reason:
            issues.append({
                "model": "Department", "id": row["id"], "field": "parent",
                "reason": reason,
            })

    _append_cycle_cuts(
        departments, edge_field="parent_id", model="Department", issue_field="parent",
        reason="parent_cycle", issues=issues,
    )

    for row in employees:
        if row["department_id"] is not None:
            department = department_by_id.get(row["department_id"])
            if department is None or department["company_id"] != row["company_id"]:
                issues.append({
                    "model": "EmployeeProfile", "id": row["id"], "field": "department",
                    "reason": "invalid_department_company",
                })
        manager_id = row["manager_id"]
        if manager_id is None:
            continue
        manager = employee_by_id.get(manager_id)
        reason = None
        if manager_id == row["id"]:
            reason = "self_manager"
        elif manager is None:
            reason = "missing_manager"
        elif manager["company_id"] != row["company_id"]:
            reason = "cross_company_manager"
        elif not _row_is_active_manager(manager, today):
            reason = "inactive_manager"
        if reason:
            issues.append({
                "model": "EmployeeProfile", "id": row["id"], "field": "manager",
                "reason": reason,
            })

    _append_cycle_cuts(
        employees, edge_field="manager_id", model="EmployeeProfile", issue_field="manager",
        reason="manager_cycle", issues=issues,
    )

    deduplicated = {
        (issue["model"], issue["id"], issue["field"]): issue
        for issue in issues
    }
    return sorted(
        deduplicated.values(),
        key=lambda issue: (issue["model"], issue["id"], issue["field"]),
    )


def _row_is_active_manager(row: dict, today) -> bool:
    return (
        row["is_employee"]
        and row["user__is_active"]
        and row["account_status"] == EmployeeProfile.ACCOUNT_ACTIVATED
        and row["start_date"] <= today
        and (row["end_date"] is None or row["end_date"] >= today)
    )


def _append_cycle_cuts(
    rows: list[dict], *, edge_field: str, model: str, issue_field: str,
    reason: str, issues: list[dict],
) -> None:
    edges = {row["id"]: row[edge_field] for row in rows}
    finished: set[int] = set()
    cuts: set[int] = set()
    for start_id in edges:
        if start_id in finished:
            continue
        path: list[int] = []
        positions: dict[int, int] = {}
        current_id = start_id
        while current_id in edges and current_id not in finished:
            if current_id in positions:
                cuts.add(max(path[positions[current_id]:]))
                break
            positions[current_id] = len(path)
            path.append(current_id)
            current_id = edges[current_id]
        finished.update(path)
    issues.extend({
        "model": model, "id": row_id, "field": issue_field, "reason": reason,
    } for row_id in cuts)


@transaction.atomic
def repair_hierarchy_issues() -> int:
    """Clear only invalid relationship edges; callers must require explicit approval."""
    lock_organizational_hierarchy()
    issues = hierarchy_issues()
    grouped: dict[tuple[str, int], set[str]] = defaultdict(set)
    for issue in issues:
        grouped[(issue["model"], issue["id"])].add(issue["field"])
    pending = list(grouped.items())
    repaired = 0
    while pending:
        remaining = []
        progress = False
        for (model_name, pk), fields in pending:
            model = Department if model_name == "Department" else EmployeeProfile
            try:
                instance = model.objects.get(pk=pk)
                for field in fields:
                    setattr(instance, f"{field}_id", None)
                instance.save(update_fields=list(fields))
            except (Department.DoesNotExist, EmployeeProfile.DoesNotExist):
                continue
            except ValidationError:
                remaining.append(((model_name, pk), fields))
                continue
            repaired += len(fields)
            progress = True
        if not progress:
            raise ValidationError(
                {"hierarchy": f"{len(remaining)} invalid relationship(s) could not be repaired safely"}
            )
        pending = remaining
    return repaired
