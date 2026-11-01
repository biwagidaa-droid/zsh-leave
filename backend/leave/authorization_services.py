from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404

from .models import (
    AuditEvent,
    Company,
    Department,
    EmployeeProfile,
    OrganizationSite,
    RoleAssignment,
)


@transaction.atomic
def grant_role_assignment(*, actor, user_id: int, role: str, scope: str,
                          company_id: int | None = None, site_id: int | None = None,
                          department_id: int | None = None,
                          employee_id: int | None = None) -> RoleAssignment:
    user_model = get_user_model()
    target_user = user_model.objects.select_for_update().get(pk=user_id, is_active=True)
    if target_user.pk == actor.pk:
        raise ValidationError({"userId": "نقش‌های خود را نمی‌توانید تغییر دهید"})

    company = Company.objects.get(pk=company_id) if company_id is not None else None
    site = OrganizationSite.objects.get(pk=site_id) if site_id is not None else None
    department = Department.objects.get(pk=department_id) if department_id is not None else None
    employee = EmployeeProfile.objects.select_related("company").get(
        pk=employee_id,
    ) if employee_id is not None else None
    assignment = RoleAssignment(
        user=target_user,
        role=role,
        scope=scope,
        company=company,
        site=site,
        department=department,
        employee=employee,
        created_by=actor,
    )
    assignment.save()
    AuditEvent.objects.create(
        actor=actor,
        origin="authorization",
        action="role.assignment.granted",
        entity="RoleAssignment",
        entity_id=str(assignment.pk),
        before=None,
        after={
            "userId": target_user.pk,
            "role": assignment.role,
            "scope": assignment.scope,
            "companyId": assignment.company_id,
            "siteId": assignment.site_id,
            "departmentId": assignment.department_id,
            "employeeId": assignment.employee_id,
        },
        reason="",
    )
    return assignment


@transaction.atomic
def revoke_role_assignment(*, actor, assignment_id: int) -> None:
    active_assignments = list(
        RoleAssignment.objects.select_for_update().filter(is_active=True).order_by("pk")
    )
    assignment = next((item for item in active_assignments if item.pk == assignment_id), None)
    if assignment is None:
        raise Http404
    if assignment.user_id == actor.pk:
        raise ValidationError({"assignment": "نقش‌های خود را نمی‌توانید لغو کنید"})
    before = {
        "userId": assignment.user_id,
        "role": assignment.role,
        "scope": assignment.scope,
        "companyId": assignment.company_id,
        "siteId": assignment.site_id,
        "departmentId": assignment.department_id,
        "employeeId": assignment.employee_id,
    }
    if assignment.role == RoleAssignment.ROLE_ADMIN:
        active_admins = [
            item for item in active_assignments
            if item.role == RoleAssignment.ROLE_ADMIN
            and item.scope == RoleAssignment.SCOPE_GLOBAL
        ]
        if len(active_admins) == 1 and not actor.is_superuser:
            raise ValidationError({"assignment": "آخرین مدیر سامانه را نمی‌توان لغو کرد"})
    assignment.is_active = False
    assignment.revoked_by = actor
    assignment.save(update_fields=["is_active", "revoked_by", "updated_at"])
    AuditEvent.objects.create(
        actor=actor,
        origin="authorization",
        action="role.assignment.revoked",
        entity="RoleAssignment",
        entity_id=str(assignment.pk),
        before=before,
        after=None,
        reason="",
    )


def assignment_payload(assignment: RoleAssignment) -> dict:
    return {
        "id": assignment.pk,
        "userId": assignment.user_id,
        "role": assignment.role,
        "scope": assignment.scope,
        "companyId": assignment.company_id,
        "siteId": assignment.site_id,
        "departmentId": assignment.department_id,
        "employeeId": assignment.employee_id,
        "isActive": assignment.is_active,
    }
