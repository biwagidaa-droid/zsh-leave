import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from leave.authorization import (
    ADMIN,
    EXEC,
    HR,
    MANAGER,
    READ_COMPANY_CALENDAR,
    authorization_context,
    can_decide_leave_request,
    can_view_leave_request,
    has_permission,
    scoped_employees,
    scoped_leave_requests,
)
from leave.models import (
    AuditEvent,
    Company,
    Department,
    EmployeeProfile,
    LeaveRequest,
    LeaveType,
    OrganizationSite,
    RoleAssignment,
)


class RBACPolicyTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.company_a = Company.objects.create(code="A", name="Company A")
        self.company_b = Company.objects.create(code="B", name="Company B")
        self.site_a = OrganizationSite.objects.create(
            company=self.company_a, code="A1", name="A site",
        )
        self.site_b = OrganizationSite.objects.create(
            company=self.company_b, code="B1", name="B site",
        )
        self.employee_user = user_model.objects.create_user(username="employee")
        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user, company=self.company_a, site=self.site_a,
            personnel_code="A-1", start_date=dt.date(2020, 1, 1),
        )
        self.manager_user = user_model.objects.create_user(username="old-manager")
        self.manager = EmployeeProfile.objects.create(
            user=self.manager_user, company=self.company_a, personnel_code="A-2",
            start_date=dt.date(2020, 1, 1),
        )
        self.next_manager_user = user_model.objects.create_user(username="new-manager")
        self.next_manager = EmployeeProfile.objects.create(
            user=self.next_manager_user, company=self.company_a, personnel_code="A-3",
            start_date=dt.date(2020, 1, 1),
        )
        self.employee.manager = self.manager
        self.employee.save(update_fields=["manager"])
        self.other_user = user_model.objects.create_user(username="other-company")
        self.other_employee = EmployeeProfile.objects.create(
            user=self.other_user, company=self.company_b, site=self.site_b,
            personnel_code="B-1", start_date=dt.date(2020, 1, 1),
        )
        self.hr_user = user_model.objects.create_user(username="hr-a")
        self.hr_employee = EmployeeProfile.objects.create(
            user=self.hr_user, company=self.company_a, personnel_code="A-4",
            start_date=dt.date(2020, 1, 1),
        )
        self.hr_assignment = RoleAssignment.objects.create(
            user=self.hr_user, role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY, company=self.company_a,
        )
        self.exec_user = user_model.objects.create_user(username="exec-a")
        RoleAssignment.objects.create(
            user=self.exec_user, role=RoleAssignment.ROLE_EXEC,
            scope=RoleAssignment.SCOPE_COMPANY, company=self.company_a,
        )
        self.leave_type = LeaveType.objects.create(
            key="annual", label_fa="Annual", employee_requestable=True,
        )
        self.request_a = LeaveRequest.objects.create(
            employee=self.employee, manager_snapshot=self.manager, leave_type=self.leave_type,
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 2),
            working_days=Decimal("1"), status="APPROVED",
        )
        self.request_b = LeaveRequest.objects.create(
            employee=self.other_employee, leave_type=self.leave_type,
            start_date=dt.date(2026, 11, 3), end_date=dt.date(2026, 11, 3),
            working_days=Decimal("1"), status="APPROVED",
        )

    def test_scoped_hr_and_employee_querysets_exclude_other_companies(self):
        context = authorization_context(self.hr_user)
        self.assertEqual(list(scoped_leave_requests(context)), [self.request_a])
        self.assertEqual(
            set(scoped_employees(context).values_list("pk", flat=True)),
            {self.employee.pk, self.manager.pk, self.next_manager.pk, self.hr_employee.pk},
        )
        self.assertTrue(has_permission(
            context, READ_COMPANY_CALENDAR, company_id=self.company_a.pk,
        ))
        self.assertFalse(has_permission(
            context, READ_COMPANY_CALENDAR, company_id=self.company_b.pk,
        ))
        self.assertFalse(context.has_scope(
            HR, company_id=self.company_b.pk, site_id=self.site_b.pk,
        ))

    def test_site_and_department_scope_do_not_expand_to_company(self):
        assignment = self.hr_assignment
        assignment.scope = RoleAssignment.SCOPE_SITE
        assignment.site = self.site_a
        assignment.company = self.company_a
        assignment.save()
        foreign_site_user = get_user_model().objects.create_user(username="foreign-site-record")
        foreign_site_employee = EmployeeProfile.objects.create(
            user=foreign_site_user, company=self.company_b, site=self.site_a,
            personnel_code="B-2", start_date=dt.date(2020, 1, 1),
        )
        LeaveRequest.objects.create(
            employee=foreign_site_employee, leave_type=self.leave_type,
            start_date=dt.date(2026, 11, 4), end_date=dt.date(2026, 11, 4),
            working_days=Decimal("1"), status="APPROVED",
        )
        context = authorization_context(self.hr_user)
        self.assertEqual(list(scoped_leave_requests(context)), [self.request_a])
        self.assertNotIn(foreign_site_employee.pk, scoped_employees(context).values_list("pk", flat=True))
        self.assertTrue(context.has_scope(
            HR, company_id=self.company_a.pk, site_id=self.site_a.pk,
        ))
        self.assertFalse(context.has_scope(
            HR, company_id=self.company_b.pk, site_id=self.site_a.pk,
        ))
        self.assertFalse(context.has_scope(
            HR, company_id=self.company_a.pk, site_id=None,
        ))
        with self.assertRaises(ValidationError):
            RoleAssignment.objects.create(
                user=self.hr_user, role=RoleAssignment.ROLE_HR,
                scope=RoleAssignment.SCOPE_SITE, company=self.company_b, site=self.site_a,
            )

    def test_department_and_employee_scopes_are_narrower_than_company(self):
        department_a = Department.objects.create(
            company=self.company_a, code="A-HR", name="A HR",
        )
        department_b = Department.objects.create(
            company=self.company_a, code="A-FIN", name="A Finance",
        )
        self.employee.department = department_a
        self.employee.save(update_fields=["department"])
        self.manager.department = department_b
        self.manager.save(update_fields=["department"])
        assignment = self.hr_assignment
        assignment.scope = RoleAssignment.SCOPE_DEPARTMENT
        assignment.department = department_a
        assignment.company = self.company_a
        assignment.save()
        context = authorization_context(self.hr_user)
        self.assertEqual(list(scoped_leave_requests(context)), [self.request_a])
        self.assertTrue(context.has_scope(
            HR, company_id=self.company_a.pk, department_id=department_a.pk,
        ))
        self.assertFalse(context.has_scope(
            HR, company_id=self.company_a.pk, department_id=department_b.pk,
        ))

        assignment.scope = RoleAssignment.SCOPE_EMPLOYEE
        assignment.department = None
        assignment.employee = self.employee
        assignment.save()
        context = authorization_context(self.hr_user)
        self.assertEqual(list(scoped_leave_requests(context)), [self.request_a])
        self.assertTrue(context.has_scope(
            HR, company_id=self.company_a.pk, employee_id=self.employee.pk,
        ))
        self.assertFalse(context.has_scope(
            HR, company_id=self.company_a.pk, employee_id=self.manager.pk,
        ))

    def test_stale_manager_snapshot_does_not_transfer_old_request_to_new_manager(self):
        self.employee.manager = self.next_manager
        self.employee.save(update_fields=["manager"])
        old_context = authorization_context(self.manager_user)
        new_context = authorization_context(self.next_manager_user)
        self.assertNotIn(MANAGER, old_context.roles)
        self.assertIn(MANAGER, new_context.roles)
        self.assertTrue(can_view_leave_request(old_context, self.request_a))
        self.assertTrue(can_decide_leave_request(old_context, self.request_a))
        self.assertFalse(can_view_leave_request(new_context, self.request_a))
        self.assertFalse(can_decide_leave_request(new_context, self.request_a))

    def test_manager_snapshot_cannot_cross_company_boundary(self):
        self.request_b.manager_snapshot = self.manager
        self.request_b.save(update_fields=["manager_snapshot"])
        context = authorization_context(self.manager_user)
        self.assertFalse(can_view_leave_request(context, self.request_b))
        self.assertFalse(scoped_leave_requests(context).filter(pk=self.request_b.pk).exists())

    def test_system_admin_and_executive_are_separated_from_individual_leave_data(self):
        admin = get_user_model().objects.create_superuser(
            username="root", email="root@example.test", password="root-password",
        )
        for user in (admin, self.exec_user):
            context = authorization_context(user)
            self.assertFalse(can_view_leave_request(context, self.request_a))
            self.assertFalse(can_decide_leave_request(context, self.request_a))
            self.assertEqual(scoped_leave_requests(context).count(), 0)
        self.assertIn(ADMIN, authorization_context(admin).roles)
        self.assertIn(EXEC, authorization_context(self.exec_user).roles)

    def test_confidential_request_can_only_be_decided_by_scoped_hr(self):
        self.request_a.leave_type.confidential = True
        self.request_a.leave_type.employee_requestable = False
        self.request_a.leave_type.save()
        self.assertFalse(can_decide_leave_request(
            authorization_context(self.manager_user), self.request_a,
        ))
        self.assertTrue(can_decide_leave_request(
            authorization_context(self.hr_user), self.request_a,
        ))


class RBACApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.company_a = Company.objects.create(code="A", name="Company A")
        self.company_b = Company.objects.create(code="B", name="Company B")
        self.user_a = user_model.objects.create_user(username="a")
        self.employee_a = EmployeeProfile.objects.create(
            user=self.user_a, company=self.company_a, personnel_code="A-1",
            start_date=dt.date(2020, 1, 1),
        )
        self.user_b = user_model.objects.create_user(username="b")
        self.employee_b = EmployeeProfile.objects.create(
            user=self.user_b, company=self.company_b, personnel_code="B-1",
            start_date=dt.date(2020, 1, 1),
        )
        self.manager_user = user_model.objects.create_user(username="manager")
        self.manager = EmployeeProfile.objects.create(
            user=self.manager_user, company=self.company_a, personnel_code="A-3",
            start_date=dt.date(2020, 1, 1),
        )
        self.hr_user = user_model.objects.create_user(username="hr")
        self.hr_employee = EmployeeProfile.objects.create(
            user=self.hr_user, company=self.company_a, personnel_code="A-2",
            start_date=dt.date(2020, 1, 1),
        )
        RoleAssignment.objects.create(
            user=self.hr_user, role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY, company=self.company_a,
        )
        self.admin = user_model.objects.create_superuser(
            username="admin", email="admin@example.test", password="admin-password",
        )
        self.client = APIClient()

    def test_company_calendar_is_server_scoped_and_hr_group_alone_is_not_authority(self):
        leave_type = LeaveType.objects.create(key="annual", label_fa="Annual")
        for employee in (self.employee_a, self.employee_b):
            LeaveRequest.objects.create(
                employee=employee, leave_type=leave_type,
                start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 2),
                working_days=Decimal("1"), status="APPROVED",
            )
        self.client.force_authenticate(self.hr_user)
        response = self.client.get(
            "/api/v1/calendar/events/",
            {"from": "2026-11-01", "to": "2026-11-30", "scope": "org"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["employeeId"] for row in response.data}, {self.employee_a.pk})

        group_only_user = get_user_model().objects.create_user(username="legacy-group-only")
        EmployeeProfile.objects.create(
            user=group_only_user, company=self.company_a, personnel_code="A-4",
            start_date=dt.date(2020, 1, 1),
        )
        group_only_user.groups.add(Group.objects.create(name="HR"))
        self.client.force_authenticate(group_only_user)
        denied = self.client.get(
            "/api/v1/calendar/events/",
            {"from": "2026-11-01", "to": "2026-11-30", "scope": "org"},
        )
        self.assertEqual(denied.status_code, 403)

    def test_manager_team_calendar_does_not_cross_company_even_with_forged_snapshot(self):
        self.employee_a.manager = self.manager
        self.employee_a.save(update_fields=["manager"])
        leave_type = LeaveType.objects.create(key="annual", label_fa="Annual")
        for employee in (self.employee_a, self.employee_b):
            LeaveRequest.objects.create(
                employee=employee, manager_snapshot=self.manager, leave_type=leave_type,
                start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 2),
                working_days=Decimal("1"), status="APPROVED",
            )
        self.client.force_authenticate(self.manager_user)
        response = self.client.get(
            "/api/v1/calendar/events/",
            {"from": "2026-11-01", "to": "2026-11-30", "scope": "team"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["employeeId"] for row in response.data}, {self.employee_a.pk})

    def test_calendar_api_never_exposes_confidential_canary_fields(self):
        canary = ["MEDICAL_CANARY_TYPE", "MEDICAL_CANARY_LABEL", "MEDICAL_CANARY_REASON"]
        confidential_type = LeaveType.objects.create(
            key=canary[0], label_fa=canary[1], confidential=True,
            employee_requestable=False,
        )
        LeaveRequest.objects.create(
            employee=self.employee_a, leave_type=confidential_type,
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 2),
            working_days=Decimal("1"), status="APPROVED", reason=canary[2],
        )
        for user, scope in ((self.user_a, "me"), (self.hr_user, "org")):
            self.client.force_authenticate(user)
            response = self.client.get(
                "/api/v1/calendar/events/",
                {"from": "2026-11-01", "to": "2026-11-30", "scope": scope},
            )
            self.assertEqual(response.status_code, 200)
            output = str(response.data)
            for value in canary:
                self.assertNotIn(value, output)

    def test_employee_workday_idor_returns_nondisclosing_404(self):
        self.client.force_authenticate(self.user_a)
        response = self.client.get(
            "/api/v1/working-days/estimate",
            {"start": "2026-11-02", "end": "2026-11-02", "employee": self.employee_b.pk},
        )
        self.assertEqual(response.status_code, 404)

    def test_client_cannot_assign_roles_and_admin_cannot_self_escalate(self):
        self.client.force_authenticate(self.hr_user)
        denied = self.client.post(
            "/api/v1/admin/role-assignments/",
            {"userId": self.hr_user.pk, "role": "admin", "scope": "global"},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.admin)
        self_escalation = self.client.post(
            "/api/v1/admin/role-assignments/",
            {"userId": self.admin.pk, "role": "hr", "scope": "company",
             "companyId": self.company_b.pk},
            format="json",
        )
        self.assertEqual(self_escalation.status_code, 400)
        self.assertFalse(RoleAssignment.objects.filter(
            user=self.admin, role="hr", company=self.company_b, is_active=True,
        ).exists())

    def test_role_grant_revoke_is_audited_and_takes_effect_immediately(self):
        self.client.force_authenticate(self.admin)
        granted = self.client.post(
            "/api/v1/admin/role-assignments/",
            {"userId": self.user_b.pk, "role": "hr", "scope": "company",
             "companyId": self.company_b.pk},
            format="json",
        )
        self.assertEqual(granted.status_code, 201)
        assignment_id = granted.data["id"]
        self.assertEqual(
            AuditEvent.objects.filter(entity="RoleAssignment", action="role.assignment.granted").count(),
            1,
        )
        self.assertTrue(authorization_context(self.user_b).has_scope(
            HR, company_id=self.company_b.pk,
        ))
        revoked = self.client.delete(
            f"/api/v1/admin/role-assignments/{assignment_id}/",
        )
        self.assertEqual(revoked.status_code, 204)
        self.assertFalse(authorization_context(self.user_b).has_role(HR))
        self.assertEqual(
            AuditEvent.objects.filter(entity="RoleAssignment", action="role.assignment.revoked").count(),
            1,
        )

    def test_role_assignment_payload_cannot_smuggle_fields_or_cross_company_site(self):
        site_a = OrganizationSite.objects.create(
            company=self.company_a, code="A1", name="A site",
        )
        self.client.force_authenticate(self.admin)
        extra_field = self.client.post(
            "/api/v1/admin/role-assignments/",
            {"userId": self.user_b.pk, "role": "hr", "scope": "company",
             "companyId": self.company_b.pk, "is_superuser": True},
            format="json",
        )
        self.assertEqual(extra_field.status_code, 400)
        invalid_scope = self.client.post(
            "/api/v1/admin/role-assignments/",
            {"userId": self.user_b.pk, "role": "hr", "scope": "site",
             "companyId": self.company_b.pk, "siteId": site_a.pk},
            format="json",
        )
        self.assertEqual(invalid_scope.status_code, 400)
        self.assertFalse(RoleAssignment.objects.filter(user=self.user_b).exists())

    def test_system_admin_configuration_role_does_not_grant_leave_data(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(
            "/api/v1/calendar/events/",
            {"from": "2026-11-01", "to": "2026-11-30", "scope": "org"},
        )
        self.assertEqual(response.status_code, 403)
