import datetime as dt
import json
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import resolve
from rest_framework.test import APIClient

from leave.entitlement_services import create_entitlement
from leave.models import (
    Company,
    Department,
    EmployeeProfile,
    LeaveRequest,
    LeaveRequestEvent,
    LeaveType,
    RoleAssignment,
    SystemSetting,
)


class FrontendApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.company = Company.objects.create(code="FRONTEND", name="Frontend company")
        self.department = Department.objects.create(
            company=self.company, code="OPS", name="Operations",
        )
        self.hr_user = user_model.objects.create_user(username="frontend-hr")
        self.employee_user = user_model.objects.create_user(username="frontend-employee")
        self.hr = EmployeeProfile.objects.create(
            user=self.hr_user, company=self.company, department=self.department,
            personnel_code="HR-1", start_date=dt.date(2020, 1, 1),
        )
        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user, company=self.company, department=self.department,
            personnel_code="E-1", start_date=dt.date(2020, 1, 1),
        )
        RoleAssignment.objects.create(
            user=self.hr_user, role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY, company=self.company,
        )
        self.leave_type = LeaveType.objects.create(
            key="annual", label_fa="استحقاقی", counts_against_balance=True,
        )
        self.confidential_type = LeaveType.objects.create(
            key="medical", label_fa="محرمانه‌پزشکی", counts_against_balance=True,
            employee_requestable=False, confidential=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.hr_user)

    def test_frontend_http_client_paths_resolve_to_backend_routes(self):
        routes = {
            "/api/v1/auth/login": "auth-login",
            "/api/v1/auth/logout": "auth-logout",
            "/api/v1/auth/me": "auth-me",
            "/api/v1/auth/password": "auth-password",
            "/api/v1/leave-types/": "leave-types",
            "/api/v1/leave-types/1/": "leave-type-detail",
            "/api/v1/leave-requests/": "leave-requests",
            "/api/v1/leave-requests/1/": "leave-request-detail",
            "/api/v1/leave-requests/1/approve": "leave-request-action",
            "/api/v1/leave-requests/1/comments/": "leave-request-comments",
            "/api/v1/leave-requests/1/attachments/": "leave-request-attachments",
            "/api/v1/leave-requests/1/attachments/2/": "leave-request-attachment-download",
            "/api/v1/balances/": "balances",
            "/api/v1/entitlements/": "entitlements",
            "/api/v1/entitlements/1/adjust": "entitlement-adjustment",
            "/api/v1/entitlements/import/": "entitlements-import",
            "/api/v1/hr/absences/": "hr-absence",
            "/api/v1/calendar/events/": "calendar-events",
            "/api/v1/calendar/holidays/": "calendar-holidays",
            "/api/v1/holidays/": "holidays",
            "/api/v1/holidays/1/": "holiday-detail",
            "/api/v1/notifications/": "notifications",
            "/api/v1/notifications/1/read": "notification-read",
            "/api/v1/employees/": "employees",
            "/api/v1/employees/1/": "employee-detail",
            "/api/v1/employees/1/contract-periods/": "employee-contracts",
            "/api/v1/companies/": "companies",
            "/api/v1/companies/1/": "company-detail",
            "/api/v1/departments/": "departments",
            "/api/v1/departments/1/": "department-detail",
            "/api/v1/coverage/": "coverage",
            "/api/v1/reports/absences": "reports",
            "/api/v1/admin/settings/": "admin-settings",
            "/api/v1/admin/jobs/": "admin-jobs",
            "/api/v1/audit/events/": "audit-events",
            "/api/v1/ready/": "ready",
            "/api/v1/working-days/estimate": "working-days-estimate",
            "/api/v1/policy/client": "client-policy",
            "/api/v1/hr/bradford-notes/": "bradford-notes",
        }
        for path, route_name in routes.items():
            with self.subTest(path=path):
                self.assertEqual(resolve(path).url_name, route_name)

    def test_hr_pages_read_real_leave_and_organization_data(self):
        entitlement = create_entitlement(
            employee=self.employee, leave_type=self.leave_type, year=1405,
            base_days=Decimal("20"), actor=self.hr_user, reason="opening",
            idempotency_key="frontend-api-opening",
        )

        self.assertEqual(self.client.get("/api/v1/leave-types/").status_code, 200)
        employees = self.client.get("/api/v1/employees/").json()
        self.assertEqual({row["id"] for row in employees}, {self.hr.pk, self.employee.pk})
        self.assertEqual(self.client.get("/api/v1/companies/").json()[0]["id"], self.company.pk)
        self.assertEqual(self.client.get("/api/v1/departments/").json()[0]["id"], self.department.pk)

        balance = self.client.get("/api/v1/balances/?year=1405&employee=%s" % self.employee.pk)
        self.assertEqual(balance.status_code, 200)
        self.assertEqual(balance.json()[0]["remaining"], "20.0")
        self.assertEqual(self.client.get("/api/v1/entitlements/?year=1405").json()[0]["id"], entitlement.pk)

        contract = self.client.post(
            f"/api/v1/employees/{self.employee.pk}/contract-periods/",
            {
                "employeeId": self.employee.pk, "start": "2026-01-01", "end": None,
                "workDays": [5, 6, 0, 1, 2], "contractPercent": 100,
            },
            format="json",
        )
        self.assertEqual(contract.status_code, 201, contract.content)
        self.assertEqual(
            self.client.get(f"/api/v1/employees/{self.employee.pk}/contract-periods/").json()[0]["workDays"],
            [5, 6, 0, 1, 2],
        )

    def test_confidential_balances_require_hr_scope(self):
        create_entitlement(
            employee=self.employee, leave_type=self.leave_type, year=1405,
            base_days=Decimal("20"), actor=self.hr_user, reason="opening",
            idempotency_key="privacy-annual",
        )
        create_entitlement(
            employee=self.employee, leave_type=self.confidential_type, year=1405,
            base_days=Decimal("4"), actor=self.hr_user, reason="opening",
            idempotency_key="privacy-confidential",
        )

        self.client.force_authenticate(self.employee_user)
        own = self.client.get(f"/api/v1/balances/?year=1405&employee={self.employee.pk}")
        self.assertEqual(own.status_code, 200)
        self.assertEqual([row["leaveTypeKey"] for row in own.json()], ["annual"])
        self.assertNotIn("محرمانه", own.content.decode())

        manager_user = get_user_model().objects.create_user(username="privacy-manager")
        manager = EmployeeProfile.objects.create(
            user=manager_user, company=self.company, department=self.department,
            personnel_code="M-1", start_date=dt.date(2020, 1, 1),
        )
        self.employee.manager = manager
        self.employee.save(update_fields=["manager"])
        self.client.force_authenticate(manager_user)
        team = self.client.get(f"/api/v1/balances/?year=1405&employee={self.employee.pk}")
        self.assertEqual(team.status_code, 200)
        self.assertEqual([row["leaveTypeKey"] for row in team.json()], ["annual"])

        LeaveRequest.objects.create(
            employee=self.employee, manager_snapshot=manager, leave_type=self.confidential_type,
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 2),
            working_days=Decimal("1"), status="APPROVED",
        )
        LeaveRequest.objects.create(
            employee=self.employee, manager_snapshot=manager, leave_type=self.leave_type,
            start_date=dt.date(2026, 11, 3), end_date=dt.date(2026, 11, 3),
            working_days=Decimal("1"), status="APPROVED",
        )
        coverage = self.client.get(
            "/api/v1/coverage/?from=2026-11-02&to=2026-11-03",
        )
        self.assertEqual(coverage.status_code, 200)
        coverage_by_day = {row["date"]: row["awayCount"] for row in coverage.json()}
        self.assertEqual(coverage_by_day["2026-11-02"], 0)
        self.assertEqual(coverage_by_day["2026-11-03"], 1)

        self.client.force_authenticate(self.hr_user)
        scoped_hr = self.client.get(f"/api/v1/balances/?year=1405&employee={self.employee.pk}")
        self.assertEqual(scoped_hr.status_code, 200)
        self.assertEqual(
            {row["leaveTypeKey"] for row in scoped_hr.json()}, {"annual", "medical"},
        )
        hr_coverage = self.client.get("/api/v1/coverage/?from=2026-11-02&to=2026-11-02")
        self.assertEqual(hr_coverage.status_code, 200)
        self.assertEqual(hr_coverage.json()[0]["awayCount"], 1)

        other_company = Company.objects.create(code="PRIVACY-2", name="Other company")
        other_employee_user = get_user_model().objects.create_user(username="privacy-other")
        other_employee = EmployeeProfile.objects.create(
            user=other_employee_user, company=other_company, personnel_code="E-2",
            start_date=dt.date(2020, 1, 1),
        )
        other_hr_user = get_user_model().objects.create_user(username="privacy-other-hr")
        RoleAssignment.objects.create(
            user=other_hr_user, role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY, company=other_company,
        )
        self.client.force_authenticate(other_hr_user)
        out_of_scope = self.client.get(
            f"/api/v1/balances/?year=1405&employee={self.employee.pk}",
        )
        self.assertEqual(out_of_scope.status_code, 404)

        admin = get_user_model().objects.create_superuser(
            username="privacy-admin", password="unused",
        )
        self.client.force_authenticate(admin)
        admin_response = self.client.get(
            f"/api/v1/balances/?year=1405&employee={other_employee.pk}",
        )
        self.assertEqual(admin_response.status_code, 404)

    def test_entitlements_hide_confidential_data_outside_hr_scope(self):
        create_entitlement(
            employee=self.employee, leave_type=self.confidential_type, year=1405,
            base_days=Decimal("4"), actor=self.hr_user, reason="opening",
            idempotency_key="privacy-entitlement-in-scope",
        )
        self.client.force_authenticate(self.employee_user)
        self.assertEqual(self.client.get("/api/v1/entitlements/?year=1405").status_code, 403)

        self.client.force_authenticate(self.hr_user)
        in_scope = self.client.get("/api/v1/entitlements/?year=1405")
        self.assertEqual(in_scope.status_code, 200)
        self.assertEqual([row["leaveTypeKey"] for row in in_scope.json()], ["medical"])

        other_company = Company.objects.create(code="ENT-OTHER", name="Other company")
        other_employee_user = get_user_model().objects.create_user(username="entitlement-other")
        other_employee = EmployeeProfile.objects.create(
            user=other_employee_user, company=other_company, personnel_code="E-3",
            start_date=dt.date(2020, 1, 1),
        )
        create_entitlement(
            employee=other_employee, leave_type=self.confidential_type, year=1405,
            base_days=Decimal("8"), actor=self.hr_user, reason="opening",
            idempotency_key="privacy-entitlement-out-of-scope",
        )
        other_hr_user = get_user_model().objects.create_user(username="entitlement-other-hr")
        RoleAssignment.objects.create(
            user=other_hr_user, role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY, company=other_company,
        )
        mixed_user = get_user_model().objects.create_user(username="entitlement-mixed")
        mixed_employee = EmployeeProfile.objects.create(
            user=mixed_user, company=self.company, department=self.department,
            personnel_code="MIXED-1", start_date=dt.date(2020, 1, 1),
        )
        RoleAssignment.objects.create(
            user=mixed_user, role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY, company=other_company,
        )
        create_entitlement(
            employee=mixed_employee, leave_type=self.leave_type, year=1405,
            base_days=Decimal("10"), actor=self.hr_user, reason="opening",
            idempotency_key="privacy-entitlement-mixed-scope",
        )
        self.client.force_authenticate(other_hr_user)
        out_of_scope = self.client.get("/api/v1/entitlements/?year=1405")
        self.assertEqual(out_of_scope.status_code, 200)
        self.assertEqual(
            {row["employeeId"] for row in out_of_scope.json()}, {other_employee.pk},
        )
        self.client.force_authenticate(mixed_user)
        mixed_scope = self.client.get("/api/v1/entitlements/?year=1405")
        self.assertEqual(mixed_scope.status_code, 200)
        self.assertEqual(
            {row["employeeId"] for row in mixed_scope.json()}, {other_employee.pk},
        )
        self.assertNotIn(mixed_employee.pk, {row["employeeId"] for row in mixed_scope.json()})

        admin = get_user_model().objects.create_superuser(
            username="entitlement-admin", password="unused",
        )
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get("/api/v1/entitlements/?year=1405").status_code, 403)

    def test_executive_reports_exclude_confidential_records_and_balances(self):
        SystemSetting.objects.create(key="privacy.min_group_size", value=2)
        second_user = get_user_model().objects.create_user(username="report-second")
        second_employee = EmployeeProfile.objects.create(
            user=second_user, company=self.company, department=self.department,
            personnel_code="E-2", start_date=dt.date(2020, 1, 1),
        )
        for employee, key in ((self.employee, "report-confidential-1"),
                              (second_employee, "report-confidential-2")):
            LeaveRequest.objects.create(
                employee=employee, leave_type=self.confidential_type,
                start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 2),
                working_days=Decimal("1"), status="APPROVED",
            )
            create_entitlement(
                employee=employee, leave_type=self.confidential_type, year=1405,
                base_days=Decimal("4"), actor=self.hr_user, reason="opening",
                idempotency_key=key,
            )
        exec_user = get_user_model().objects.create_user(username="privacy-exec")
        RoleAssignment.objects.create(
            user=exec_user, role=RoleAssignment.ROLE_EXEC,
            scope=RoleAssignment.SCOPE_COMPANY, company=self.company,
        )
        self.client.force_authenticate(exec_user)

        for kind in ("absences", "trends", "process-health", "balances"):
            with self.subTest(report=kind):
                response = self.client.get(f"/api/v1/reports/{kind}")
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("medical", json.dumps(response.json()))
                self.assertNotIn("محرمانه", response.content.decode())
                self.assertEqual(response.json()["series"], [])

        self.client.force_authenticate(self.hr_user)
        hr_absences = self.client.get("/api/v1/reports/absences")
        self.assertEqual(hr_absences.status_code, 200)
        self.assertEqual(hr_absences.json()["series"][0]["label"], "محرمانه‌پزشکی")

    def test_notifications_are_persistently_marked_read_and_notes_are_saved(self):
        request = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 2),
            working_days=Decimal("1"), status="PENDING",
        )
        event = LeaveRequestEvent.objects.create(
            request=request, actor=self.employee_user, origin="employee",
            event="submit", to_status="PENDING",
        )
        notifications = self.client.get("/api/v1/notifications/")
        self.assertEqual(notifications.status_code, 200)
        self.assertEqual(notifications.json()[0]["id"], event.pk)
        self.assertFalse(notifications.json()[0]["read"])
        self.assertEqual(
            self.client.post(f"/api/v1/notifications/{event.pk}/read").status_code, 204,
        )
        self.assertTrue(self.client.get("/api/v1/notifications/").json()[0]["read"])

        saved = self.client.post(
            "/api/v1/hr/bradford-notes/",
            {"employeeId": self.employee.pk, "body": "Reviewed with employee"},
            format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertEqual(self.client.get("/api/v1/hr/bradford-notes/").json()[0]["body"],
                         "Reviewed with employee")

    def test_request_attachments_are_validated_and_downloaded_through_authorized_route(self):
        request = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=dt.date(2026, 11, 2), end_date=dt.date(2026, 11, 2),
            working_days=Decimal("1"), status="PENDING",
        )
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                upload = SimpleUploadedFile(
                    "evidence.pdf", b"%PDF-1.7\nprivate test attachment",
                    content_type="application/pdf",
                )
                response = self.client.post(
                    f"/api/v1/leave-requests/{request.pk}/attachments/",
                    {"file": upload}, format="multipart",
                )
                self.assertEqual(response.status_code, 201, response.content)
                listing = self.client.get(f"/api/v1/leave-requests/{request.pk}/attachments/")
                self.assertEqual(listing.status_code, 200)
                download = self.client.get(listing.json()[0]["downloadUrl"])
                self.assertEqual(download.status_code, 200)
                self.assertEqual(b"".join(download.streaming_content), b"%PDF-1.7\nprivate test attachment")

                invalid = SimpleUploadedFile(
                    "bad.pdf", b"not a pdf", content_type="application/pdf",
                )
                rejected = self.client.post(
                    f"/api/v1/leave-requests/{request.pk}/attachments/",
                    {"file": invalid}, format="multipart",
                )
                self.assertEqual(rejected.status_code, 400)

    def test_settings_and_health_routes_match_production_client_paths(self):
        admin = get_user_model().objects.create_superuser(
            username="frontend-admin", email="admin@example.test", password="test-password",
        )
        client = APIClient()
        client.force_authenticate(admin)
        settings_response = client.get("/api/v1/admin/settings/")
        self.assertEqual(settings_response.status_code, 200)
        self.assertIn("bradford.threshold_review", {row["key"] for row in settings_response.json()})
        self.assertEqual(client.get("/api/v1/ready/").status_code, 200)
        self.assertEqual(client.get("/api/v1/admin/jobs/").json(), [])
