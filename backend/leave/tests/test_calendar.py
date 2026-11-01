import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from zsh_core import settings_schema
from zsh_core.workflow import EMPLOYEE
from leave.calendar_services import (
    CalendarConfigurationError,
    calculate_working_days,
    calculate_working_minutes,
    create_calendar_holiday,
    create_policy_version,
    create_work_pattern,
    resolve_policy_version,
)
from leave.models import (
    CalendarHoliday,
    CalendarHolidayHistory,
    Company,
    Department,
    EmployeeProfile,
    LeaveRequest,
    LeaveType,
    OrganizationSite,
    PublicHoliday,
)
from leave.services import submit_request


class CalendarServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="employee", password="test-password")
        self.company = Company.objects.create(code="A", name="Company A")
        self.site = OrganizationSite.objects.create(company=self.company, code="TEH", name="Tehran")
        self.department = Department.objects.create(company=self.company, code="HR", name="HR")
        self.employee = EmployeeProfile.objects.create(
            user=self.user, company=self.company, site=self.site, department=self.department,
            personnel_code="100", start_date=dt.date(2020, 1, 1),
        )
        self.policy_values = {
            key: settings_schema.to_storable(value)
            for key, value in settings_schema.defaults().items()
            if key.startswith("policy.")
        }
        self.policy_version = create_policy_version(
            actor=self.user, scope="company", company=self.company,
            effective_from=dt.date(2026, 1, 1), values=self.policy_values,
            reason="Approved test policy",
        )

    def pattern(self, **overrides):
        values = {
            "actor": self.user,
            "name": "weekday pattern",
            "company": self.company,
            "weekdays": [0, 1, 2, 3],
            "start_time": dt.time(8, 0),
            "end_time": dt.time(17, 0),
            "break_minutes": 60,
            "effective_from": dt.date(2026, 1, 1),
            "site": self.site,
        }
        values.update(overrides)
        return create_work_pattern(**values)

    def test_calendar_calculation_uses_site_pattern_and_multiday_holiday(self):
        pattern = self.pattern()
        create_calendar_holiday(
            actor=self.user,
            title="site closure",
            start_date=dt.date(2026, 11, 3),
            end_date=dt.date(2026, 11, 4),
            scope="site",
            company=self.company,
            site=self.site,
            holiday_kind="temporary",
        )

        result = calculate_working_days(
            employee=self.employee,
            start=dt.date(2026, 11, 2),
            end=dt.date(2026, 11, 7),
            policy_version=self.policy_version,
        )

        self.assertEqual(result.days, Decimal("2"))
        self.assertEqual(result.policy_version_id, self.policy_version.pk)
        self.assertEqual(result.work_pattern_ids, (pattern.pk,))
        self.assertEqual(calculate_working_minutes(employee=self.employee, on_date=dt.date(2026, 11, 2)), 480)
        self.assertEqual(calculate_working_minutes(employee=self.employee, on_date=dt.date(2026, 11, 3)), 0)

    def test_weekly_off_counting_uses_selected_policy_version(self):
        self.pattern()
        values = dict(self.policy_values)
        values["policy.leave_day_counting"] = "INCLUDE_WEEKLY_OFF_INSIDE"
        policy = create_policy_version(
            actor=self.user, scope="employee", company=self.company, employee=self.employee,
            effective_from=dt.date(2026, 11, 1), values=values,
            reason="Approved individual policy",
        )
        result = calculate_working_days(
            employee=self.employee,
            start=dt.date(2026, 11, 2),
            end=dt.date(2026, 11, 10),
            policy_version=policy,
        )
        self.assertEqual(result.days, Decimal("7"))

    def test_policy_priority_and_effective_versioning(self):
        company_values = dict(self.policy_values)
        company_values["policy.annual_days_per_month"] = "3"
        company_version = create_policy_version(
            actor=self.user, scope="company", company=self.company,
            effective_from=dt.date(2026, 10, 1), values=company_values,
            reason="Approved company policy",
        )
        employee_values = dict(self.policy_values)
        employee_values["policy.annual_days_per_month"] = "4"
        employee_version = create_policy_version(
            actor=self.user, scope="employee", company=self.company, employee=self.employee,
            effective_from=dt.date(2026, 11, 1), values=employee_values,
            reason="Approved employee exception",
        )

        self.assertEqual(resolve_policy_version(self.employee, dt.date(2026, 10, 15)).pk,
                         company_version.pk)
        self.assertEqual(resolve_policy_version(self.employee, dt.date(2026, 11, 2)).pk,
                         employee_version.pk)
        self.assertEqual(self.policy_version.version, 1)
        self.assertEqual(company_version.version, 2)

    def test_policy_version_is_immutable_and_requires_reason(self):
        self.policy_version.values = {"policy.leave_calendar": "gregorian"}
        with self.assertRaises(PermissionError):
            self.policy_version.save()
        with self.assertRaises(ValidationError):
            create_policy_version(
                actor=self.user, scope="company", company=self.company,
                effective_from=dt.date(2027, 1, 1), values=self.policy_values, reason=" ",
            )

    def test_work_pattern_rejects_overlap_and_invalid_cross_company_scope(self):
        self.pattern()
        with self.assertRaises(ValidationError):
            self.pattern(name="overlap", effective_from=dt.date(2026, 10, 1))
        other_company = Company.objects.create(code="B", name="Company B")
        with self.assertRaises(ValidationError):
            self.pattern(name="wrong site", company=other_company, site=self.site)

    def test_missing_pattern_or_policy_fails_closed(self):
        with self.assertRaises(CalendarConfigurationError):
            calculate_working_days(
                employee=self.employee, start=dt.date(2026, 11, 2), end=dt.date(2026, 11, 2),
            )
        other_company = Company.objects.create(code="B", name="Company B")
        other_user = get_user_model().objects.create_user(username="no-policy")
        other_employee = EmployeeProfile.objects.create(
            user=other_user, company=other_company, personnel_code="200",
            start_date=dt.date(2020, 1, 1),
        )
        with self.assertRaises(CalendarConfigurationError):
            resolve_policy_version(other_employee, dt.date(2026, 11, 2))

    def test_leave_submission_uses_central_calculation_and_persists_policy_version(self):
        self.pattern()
        leave_type = LeaveType.objects.create(
            key="annual", label_fa="استحقاقی", employee_requestable=True, requires_approval=True,
        )
        request = submit_request(
            user=self.user, role=EMPLOYEE, employee=self.employee, leave_type=leave_type,
            start=dt.date(2026, 11, 2), end=dt.date(2026, 11, 2),
        )
        self.assertEqual(request.working_days, Decimal("1"))
        self.assertEqual(request.policy_version_id, self.policy_version.pk)
        self.assertEqual(LeaveRequest.objects.count(), 1)

    def test_leave_submission_uses_policy_effective_on_request_start(self):
        self.pattern()
        leave_type = LeaveType.objects.create(
            key="future", label_fa="مرخصی آینده", employee_requestable=True, requires_approval=True,
        )
        values = dict(self.policy_values)
        values["policy.annual_days_per_month"] = "4"
        future_policy = create_policy_version(
            actor=self.user, scope="employee", company=self.company, employee=self.employee,
            effective_from=dt.date(2026, 11, 15), values=values,
            reason="Approved future policy",
        )

        request = submit_request(
            user=self.user, role=EMPLOYEE, employee=self.employee, leave_type=leave_type,
            start=dt.date(2026, 11, 23), end=dt.date(2026, 11, 23),
        )

        self.assertEqual(request.policy_version_id, future_policy.pk)


class CalendarApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="worker", password="test-password")
        self.manager_user = user_model.objects.create_user(username="manager", password="test-password")
        self.other_user = user_model.objects.create_user(username="other", password="test-password")
        self.company_a = Company.objects.create(code="A", name="Company A")
        self.company_b = Company.objects.create(code="B", name="Company B")
        self.employee = EmployeeProfile.objects.create(
            user=self.user, company=self.company_a, personnel_code="101",
            start_date=dt.date(2020, 1, 1),
        )
        self.manager = EmployeeProfile.objects.create(
            user=self.manager_user, company=self.company_a, personnel_code="102",
            start_date=dt.date(2020, 1, 1),
        )
        self.report = EmployeeProfile.objects.create(
            user=self.other_user, company=self.company_a, personnel_code="103",
            manager=self.manager, start_date=dt.date(2020, 1, 1),
        )
        self.client = APIClient()

    def test_calendar_apis_require_authentication(self):
        response = self.client.get("/api/v1/calendar/events/", {"from": "2026-11-01", "to": "2026-11-30"})
        self.assertIn(response.status_code, (401, 403))

    def test_calendar_team_scope_is_direct_report_only_and_redacts_sensitive_type(self):
        leave_type = LeaveType.objects.create(
            key="medical", label_fa="استعلاجی", confidential=True, employee_requestable=False,
        )
        LeaveRequest.objects.create(
            employee=self.report, manager_snapshot=self.manager, leave_type=leave_type,
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 2),
            working_days=Decimal("1"), status="APPROVED", reason="sensitive reason",
        )
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.get(
            "/api/v1/calendar/events/",
            {"from": "2026-11-01", "to": "2026-11-30", "scope": "team"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["label"], "غیبت")
        self.assertNotIn("reason", response.data[0])

    def test_org_calendar_requires_company_scoped_hr_role(self):
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.get(
            "/api/v1/calendar/events/",
            {"from": "2026-11-01", "to": "2026-11-30", "scope": "org"},
        )
        self.assertEqual(response.status_code, 403)

        admin = get_user_model().objects.create_superuser(
            username="root", email="root@example.test", password="test-password",
        )
        self.client.force_authenticate(user=admin)
        response = self.client.get(
            "/api/v1/calendar/events/",
            {"from": "2026-11-01", "to": "2026-11-30", "scope": "org"},
        )
        self.assertEqual(response.status_code, 403)

    def test_hr_org_calendar_is_limited_to_hr_employee_company(self):
        hr_group = Group.objects.create(name="HR")
        self.other_user.groups.add(hr_group)
        company_b_user = get_user_model().objects.create_user(
            username="company-b-worker", password="test-password",
        )
        company_b_employee = EmployeeProfile.objects.create(
            user=company_b_user, company=self.company_b, personnel_code="201",
            start_date=dt.date(2020, 1, 1),
        )
        leave_type = LeaveType.objects.create(
            key="annual", label_fa="استحقاقی", employee_requestable=True,
        )
        for employee in (self.report, company_b_employee):
            LeaveRequest.objects.create(
                employee=employee, leave_type=leave_type,
                start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 2),
                working_days=Decimal("1"), status="APPROVED",
            )

        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(
            "/api/v1/calendar/events/",
            {"from": "2026-11-01", "to": "2026-11-30", "scope": "org"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {event["employeeId"] for event in response.data},
            {self.report.pk},
        )

    def test_holiday_list_is_scoped_to_employee_company(self):
        PublicHoliday.objects.create(
            scope="*", jalali_year=1405, jalali_month=8, jalali_day=10, label="national",
        )
        PublicHoliday.objects.create(
            scope="A", jalali_year=1405, jalali_month=8, jalali_day=11, label="company A",
        )
        PublicHoliday.objects.create(
            scope="B", jalali_year=1405, jalali_month=8, jalali_day=12, label="company B",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/v1/calendar/holidays/",
            {"from": "2026-10-31", "to": "2026-11-10"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["title"] for item in response.data},
            {"national", "company A"},
        )

    def test_superuser_can_create_and_soft_deactivate_multiday_holiday(self):
        admin = get_user_model().objects.create_superuser(
            username="root", email="root@example.test", password="test-password",
        )
        self.client.force_authenticate(user=admin)
        created = self.client.post(
            "/api/v1/calendar/holidays/manage/",
            {
                "title": "temporary closure",
                "start": "2026-11-03",
                "end": "2026-11-04",
                "scope": "company",
                "companyId": self.company_a.pk,
                "kind": "temporary",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        holiday_id = created.data["id"]
        response = self.client.delete(
            f"/api/v1/calendar/holidays/manage/{holiday_id}/",
            {"reason": "closure withdrawn"},
            format="json",
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(CalendarHoliday.objects.get(pk=holiday_id).is_active)
        self.assertEqual(
            list(CalendarHolidayHistory.objects.filter(holiday_id=holiday_id).values_list("action", flat=True)),
            ["create", "deactivate"],
        )

    def test_non_superuser_cannot_manage_holidays_or_policies(self):
        self.client.force_authenticate(user=self.manager_user)
        holiday_response = self.client.post(
            "/api/v1/calendar/holidays/manage/",
            {"title": "x", "start": "2026-11-01", "end": "2026-11-01", "scope": "national"},
            format="json",
        )
        policy_response = self.client.post("/api/v1/calendar/policies/", {}, format="json")
        self.assertEqual(holiday_response.status_code, 403)
        self.assertEqual(policy_response.status_code, 403)
