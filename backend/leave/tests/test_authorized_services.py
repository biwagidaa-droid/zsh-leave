import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from leave.models import Company, EmployeeProfile, LeaveRequest, LeaveType, RoleAssignment
from leave.services import apply_event, submit_request
from zsh_core import workflow as wf


class AuthorizedLeaveServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.company_a = Company.objects.create(code="A", name="Company A")
        self.company_b = Company.objects.create(code="B", name="Company B")
        self.employee_user = user_model.objects.create_user(username="employee")
        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user, company=self.company_a, personnel_code="A-1",
            start_date=dt.date(2020, 1, 1),
        )
        self.manager_user = user_model.objects.create_user(username="manager")
        self.manager = EmployeeProfile.objects.create(
            user=self.manager_user, company=self.company_a, personnel_code="A-2",
            start_date=dt.date(2020, 1, 1),
        )
        self.next_manager_user = user_model.objects.create_user(username="next-manager")
        self.next_manager = EmployeeProfile.objects.create(
            user=self.next_manager_user, company=self.company_a, personnel_code="A-3",
            start_date=dt.date(2020, 1, 1),
        )
        self.employee.manager = self.manager
        self.employee.save(update_fields=["manager"])
        self.hr_user = user_model.objects.create_user(username="hr")
        RoleAssignment.objects.create(
            user=self.hr_user, role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY, company=self.company_a,
        )
        self.other_user = user_model.objects.create_user(username="other-company")
        self.other_employee = EmployeeProfile.objects.create(
            user=self.other_user, company=self.company_b, personnel_code="B-1",
            start_date=dt.date(2020, 1, 1),
        )
        self.admin = user_model.objects.create_superuser(
            username="root", email="root@example.test", password="root-password",
        )
        self.leave_type = LeaveType.objects.create(
            key="annual", label_fa="Annual", employee_requestable=True,
        )

    def make_request(self, *, employee=None, manager=None, confidential=False):
        leave_type = self.leave_type
        if confidential:
            leave_type = LeaveType.objects.create(
                key="medical", label_fa="Medical", confidential=True,
                employee_requestable=False,
            )
        return LeaveRequest.objects.create(
            employee=employee or self.employee,
            manager_snapshot=manager,
            leave_type=leave_type,
            start_date=dt.date(2026, 11, 2),
            end_date=dt.date(2026, 11, 2),
            working_days=Decimal("1"),
            status=wf.PENDING,
        )

    def test_submit_request_does_not_accept_a_caller_supplied_role(self):
        with self.assertRaises(TypeError):
            submit_request(
                user=self.manager_user, role=wf.HR, employee=self.employee,
                leave_type=self.leave_type, start=dt.date(2026, 11, 2),
                end=dt.date(2026, 11, 2),
            )
        with self.assertRaises(wf.PermissionDenied):
            submit_request(
                user=self.manager_user, employee=self.employee, leave_type=self.leave_type,
                start=dt.date(2026, 11, 2), end=dt.date(2026, 11, 2),
            )

    def test_apply_event_uses_scoped_object_selector_and_server_derived_role(self):
        request = self.make_request(manager=self.manager)
        with self.assertRaises(LeaveRequest.DoesNotExist):
            apply_event(
                request_id=request.pk, user=self.other_user, event="approve",
            )
        with self.assertRaises(LeaveRequest.DoesNotExist):
            apply_event(
                request_id=request.pk, user=self.admin, event="approve",
            )
        approved = apply_event(
            request_id=request.pk, user=self.manager_user, event="approve",
        )
        self.assertEqual(approved.status, wf.APPROVED)
        self.assertEqual(approved.decided_by_id, self.manager_user.pk)

    def test_snapshot_authorizes_old_manager_but_not_new_manager(self):
        request = self.make_request(manager=self.manager)
        self.employee.manager = self.next_manager
        self.employee.save(update_fields=["manager"])
        decided = apply_event(
            request_id=request.pk, user=self.manager_user, event="approve",
        )
        self.assertEqual(decided.status, wf.APPROVED)
        with self.assertRaises(LeaveRequest.DoesNotExist):
            apply_event(
                request_id=request.pk, user=self.next_manager_user, event="approve",
            )

    def test_confidential_decisions_cannot_be_made_by_manager(self):
        request = self.make_request(manager=self.manager, confidential=True)
        with self.assertRaises(wf.PermissionDenied):
            apply_event(
                request_id=request.pk, user=self.manager_user, event="approve",
            )
