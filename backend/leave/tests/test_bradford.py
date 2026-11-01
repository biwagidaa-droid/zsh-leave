import datetime as dt
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from leave.employment_services import organization_localdate
from leave.models import (
    CalendarHoliday,
    Company,
    Department,
    EmployeeProfile,
    LeaveRequest,
    LeaveType,
    RoleAssignment,
    SystemSetting,
    WorkPattern,
)


class BradfordReportApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.today = organization_localdate()
        self.start = self.today - dt.timedelta(days=20)
        self.end = self.today
        self.company = Company.objects.create(code="BRADFORD-A", name="Bradford A")
        self.department = Department.objects.create(
            company=self.company, code="OPS", name="Operations",
        )
        self.other_department = Department.objects.create(
            company=self.company, code="HR", name="Human resources",
        )
        user_model = get_user_model()
        self.hr_user = user_model.objects.create_user(username="bradford-hr")
        self.hr = EmployeeProfile.objects.create(
            user=self.hr_user, company=self.company, department=self.department,
            personnel_code="HR-1", start_date=dt.date(2020, 1, 1),
        )
        RoleAssignment.objects.create(
            user=self.hr_user,
            role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY,
            company=self.company,
        )
        self.employees = [
            self.make_employee(f"employee-{index}", f"E-{index}", self.department)
            for index in range(3)
        ]
        self.sick = LeaveType.objects.create(key="sick", label_fa="استعلاجی")
        self.annual = LeaveType.objects.create(key="annual", label_fa="استحقاقی")
        self.confidential = LeaveType.objects.create(
            key="private", label_fa="محرمانه‌پزشکی", confidential=True,
            employee_requestable=False,
        )
        SystemSetting.objects.create(key="privacy.min_group_size", value=2)
        SystemSetting.objects.create(key="bradford.enabled", value=True)
        SystemSetting.objects.create(key="bradford.include_types", value="sick")
        self.client = APIClient()
        self.client.force_authenticate(self.hr_user)

    def make_employee(self, username, code, department, *, start_date=None, end_date=None):
        user = get_user_model().objects.create_user(username=username)
        return EmployeeProfile.objects.create(
            user=user,
            company=department.company,
            department=department,
            personnel_code=code,
            start_date=start_date or dt.date(2020, 1, 1),
            end_date=end_date,
        )

    def request(self, employee, leave_type=None, *, start=None, end=None, days=1, status="APPROVED"):
        start = start or self.start + dt.timedelta(days=1)
        end = end or start
        return LeaveRequest.objects.create(
            employee=employee,
            leave_type=leave_type or self.sick,
            start_date=start,
            end_date=end,
            working_days=Decimal(str(days)),
            status=status,
        )

    def report(self, **params):
        return self.client.get(
            "/api/v1/reports/bradford",
            {"from": self.start.isoformat(), "to": self.end.isoformat(), **params},
        )

    def series_by_employee(self, response):
        return {row["employeeId"]: row for row in response.json()["series"]}

    def test_formula_one_spell_multiple_days_and_multiple_spells(self):
        employee = self.employees[0]
        self.request(
            employee, start=self.start + dt.timedelta(days=1),
            end=self.start + dt.timedelta(days=2), days=2,
        )
        self.request(employee, start=self.start + dt.timedelta(days=5))
        self.request(
            employee, start=self.start + dt.timedelta(days=7),
            end=self.start + dt.timedelta(days=8), days=2,
        )

        response = self.report()

        self.assertEqual(response.status_code, 200, response.content)
        row = self.series_by_employee(response)[employee.pk]
        self.assertEqual((row["spells"], row["days"], row["score"]), (3, 5, 45))
        self.assertEqual(response.json()["policy"]["formula"], "S^2 * D")
        self.assertEqual(response.json()["status"], "provisional")

    def test_consecutive_dates_merge_even_when_weekend_and_holiday(self):
        employee = self.employees[0]
        friday = self.today - dt.timedelta(days=(self.today.weekday() - 4) % 7)
        if friday == self.today:
            friday -= dt.timedelta(days=7)
        saturday = friday + dt.timedelta(days=1)
        WorkPattern.objects.create(
            name="Part-time weekday pattern",
            company=self.company,
            working_weekdays=[0, 1, 2, 3, 6],
            start_time=dt.time(9),
            end_time=dt.time(13),
            effective_from=friday - dt.timedelta(days=1),
        )
        CalendarHoliday.objects.create(
            title="Holiday",
            start_date=saturday,
            end_date=saturday,
            scope="national",
        )
        self.request(employee, start=friday)
        self.request(employee, start=saturday)

        response = self.report()

        row = self.series_by_employee(response)[employee.pk]
        self.assertEqual((row["spells"], row["days"], row["score"]), (1, 2, 2))

    def test_pending_cancelled_and_rejected_requests_do_not_count(self):
        employee = self.employees[0]
        for status in ("PENDING", "ESCALATED", "REJECTED", "CANCELLED"):
            self.request(
                employee, start=self.start + dt.timedelta(days=1),
                status=status,
            )
        response = self.report()
        row = self.series_by_employee(response)[employee.pk]
        self.assertEqual((row["spells"], row["days"], row["score"]), (0, 0, 0))

    def test_withdrawal_pending_counts_until_cancellation_is_approved(self):
        employee = self.employees[0]
        self.request(employee, status="WITHDRAWAL_PENDING")
        row = self.series_by_employee(self.report())[employee.pk]
        self.assertEqual((row["spells"], row["days"], row["score"]), (1, 1, 1))

    def test_excluded_and_confidential_types_do_not_contribute_or_leak(self):
        employee = self.employees[0]
        self.request(employee, self.annual)
        self.request(employee, self.confidential, start=self.start + dt.timedelta(days=3))
        SystemSetting.objects.filter(key="bradford.include_types").update(
            value="sick,private",
        )

        response = self.report()

        self.assertEqual(response.status_code, 200)
        row = self.series_by_employee(response)[employee.pk]
        self.assertEqual((row["spells"], row["days"], row["score"]), (0, 0, 0))
        body = response.content.decode()
        self.assertNotIn("private", body)
        self.assertNotIn("محرمانه‌پزشکی", body)
        self.assertNotIn("annual", body)

    def test_scoped_hr_and_company_boundaries_are_enforced(self):
        scoped_user = get_user_model().objects.create_user(username="department-hr")
        RoleAssignment.objects.create(
            user=scoped_user,
            role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_DEPARTMENT,
            company=self.company,
            department=self.department,
        )
        RoleAssignment.objects.create(
            user=scoped_user,
            role=RoleAssignment.ROLE_ADMIN,
            scope=RoleAssignment.SCOPE_GLOBAL,
        )
        other_dept_employee = self.make_employee(
            "other-department-employee", "OTHER-1", self.other_department,
        )
        other_company = Company.objects.create(code="BRADFORD-B", name="Bradford B")
        other_company_department = Department.objects.create(
            company=other_company, code="OPS", name="Operations",
        )
        other_company_employee = self.make_employee(
            "other-company-employee", "OTHER-COMPANY", other_company_department,
        )
        for employee in (self.employees[0], other_dept_employee, other_company_employee):
            self.request(employee)

        self.client.force_authenticate(scoped_user)
        response = self.report()

        self.assertEqual(response.status_code, 200, response.content)
        ids = {row["employeeId"] for row in response.json()["series"]}
        self.assertEqual(ids, {employee.pk for employee in self.employees} | {self.hr.pk})
        self.assertNotIn(other_dept_employee.pk, ids)
        self.assertNotIn(other_company_employee.pk, ids)

    def test_non_hr_and_executive_users_cannot_read_employee_level_scores(self):
        exec_user = get_user_model().objects.create_user(username="bradford-exec")
        RoleAssignment.objects.create(
            user=exec_user,
            role=RoleAssignment.ROLE_EXEC,
            scope=RoleAssignment.SCOPE_COMPANY,
            company=self.company,
        )
        self.client.force_authenticate(exec_user)
        self.assertEqual(self.report().status_code, 403)

        self.client.force_authenticate(self.employees[0].user)
        self.assertEqual(self.report().status_code, 403)

    def test_future_and_former_employment_are_clipped_to_the_reporting_period(self):
        former = self.make_employee(
            "former-employee", "FORMER", self.department,
            start_date=self.start + dt.timedelta(days=1),
            end_date=self.start + dt.timedelta(days=3),
        )
        future = self.make_employee(
            "future-employee", "FUTURE", self.department,
            start_date=self.end + dt.timedelta(days=1),
        )
        self.request(
            former,
            start=self.start,
            end=self.start + dt.timedelta(days=5),
            days=6,
        )
        self.request(future, start=self.end, end=self.end)

        response = self.report()

        self.assertEqual(response.status_code, 200)
        rows = self.series_by_employee(response)
        self.assertEqual((rows[former.pk]["spells"], rows[former.pk]["days"]), (1, 3))
        self.assertNotIn(future.pk, rows)

    def test_exact_reporting_boundaries_are_inclusive(self):
        employee = self.employees[0]
        self.request(employee, start=self.start, end=self.start + dt.timedelta(days=1), days=2)
        self.request(employee, start=self.end + dt.timedelta(days=1))

        response = self.report()

        row = self.series_by_employee(response)[employee.pk]
        self.assertEqual((row["spells"], row["days"], row["score"]), (1, 2, 2))

    def test_missing_policy_is_an_explicit_error_not_a_zero_score(self):
        SystemSetting.objects.filter(key="bradford.enabled").delete()

        response = self.report()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["status"], "configuration_error")
        self.assertIsNone(response.json()["policy"])
        self.assertEqual(response.json()["series"], [])
        self.assertEqual(
            response.json()["emptyStateReason"],
            "bradford_policy_not_configured",
        )

    def test_partial_day_data_withholds_all_scores(self):
        self.request(self.employees[0], days="0.5")

        response = self.report()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertEqual(response.json()["series"], [])
        self.assertEqual(
            response.json()["error"]["code"],
            "incomplete_partial_day_data",
        )

    def test_empty_eligible_dataset_has_an_explicit_reason(self):
        self.request(self.employees[0], status="PENDING")

        response = self.report()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["emptyStateReason"], "no_eligible_absences")
        self.assertEqual(
            {row["score"] for row in response.json()["series"]},
            {0},
        )

    def test_empty_employment_scope_has_an_explicit_reason(self):
        future_employee = self.make_employee(
            "future-only", "FUTURE-ONLY", self.department,
            start_date=self.end + dt.timedelta(days=1),
        )
        scoped_hr = get_user_model().objects.create_user(username="empty-scope-hr")
        RoleAssignment.objects.create(
            user=scoped_hr,
            role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_EMPLOYEE,
            company=self.company,
            employee=future_employee,
        )
        self.client.force_authenticate(scoped_hr)

        response = self.report()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "empty")
        self.assertEqual(
            response.json()["emptyStateReason"],
            "no_employees_in_period",
        )

    def test_large_population_is_paginated_without_per_employee_queries(self):
        employees = [
            self.make_employee(f"large-{index}", f"L-{index}", self.department)
            for index in range(25)
        ]
        for employee in employees:
            self.request(employee)

        with CaptureQueriesContext(connection) as queries:
            response = self.report(limit=5)

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["series"]), 5)
        self.assertEqual(payload["pagination"]["total"], 29)
        self.assertTrue(payload["pagination"]["hasMore"])
        self.assertLessEqual(len(queries), 12, json.dumps([q["sql"] for q in queries]))

    def test_report_period_and_pagination_are_validated(self):
        invalid_period = self.client.get(
            "/api/v1/reports/bradford",
            {"from": self.start.isoformat(), "to": (self.today + dt.timedelta(days=1)).isoformat()},
        )
        invalid_page = self.report(limit=201)
        self.assertEqual(invalid_period.status_code, 400)
        self.assertEqual(invalid_period.json()["status"], "invalid_request")
        self.assertEqual(invalid_page.status_code, 400)
        self.assertEqual(invalid_page.json()["emptyStateReason"], "invalid_pagination")
