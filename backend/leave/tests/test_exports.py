import csv
import datetime as dt
import io
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import resolve
from openpyxl import load_workbook
from rest_framework.test import APIClient

from leave.entitlement_services import create_entitlement
from leave.models import (
    AuditEvent,
    Company,
    Department,
    EmployeeProfile,
    LeaveRequest,
    LeaveType,
    RoleAssignment,
)


class ExportApiTests(TestCase):
    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.company = Company.objects.create(code="EXPORT-A", name="Export company A")
        self.other_company = Company.objects.create(code="EXPORT-B", name="Export company B")
        self.department = Department.objects.create(
            company=self.company, code="OPS", name="Operations",
        )
        self.other_department = Department.objects.create(
            company=self.other_company, code="OPS", name="Other operations",
        )
        self.employee_user = user_model.objects.create_user(
            username="export-employee", first_name="Own", last_name="Employee",
        )
        self.manager_user = user_model.objects.create_user(
            username="export-manager", first_name="Team", last_name="Manager",
        )
        self.hr_user = user_model.objects.create_user(
            username="export-hr", first_name="Scoped", last_name="HR",
        )
        self.other_user = user_model.objects.create_user(
            username="export-other", first_name="Other", last_name="Company",
        )
        self.colleague_user = user_model.objects.create_user(
            username="export-colleague", first_name="Same", last_name="Company",
        )
        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user, company=self.company, department=self.department,
            personnel_code="EX-A-1", start_date=dt.date(2020, 1, 1),
        )
        self.manager = EmployeeProfile.objects.create(
            user=self.manager_user, company=self.company, department=self.department,
            personnel_code="EX-A-M", start_date=dt.date(2019, 1, 1),
        )
        self.other = EmployeeProfile.objects.create(
            user=self.other_user, company=self.other_company, department=self.other_department,
            personnel_code="EX-B-1", start_date=dt.date(2020, 1, 1),
        )
        self.colleague = EmployeeProfile.objects.create(
            user=self.colleague_user, company=self.company, department=self.department,
            personnel_code="EX-A-2", start_date=dt.date(2020, 1, 1),
        )
        self.employee.manager = self.manager
        self.employee.save(update_fields=["manager"])
        RoleAssignment.objects.create(
            user=self.hr_user, role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY, company=self.company,
        )
        self.annual = LeaveType.objects.create(
            key="export-annual", label_fa="Annual leave", counts_against_balance=True,
        )
        self.confidential = LeaveType.objects.create(
            key="export-medical", label_fa="CONFIDENTIAL-TYPE",
            counts_against_balance=True, employee_requestable=False, confidential=True,
        )
        self.request = self.make_request(
            self.employee, self.annual, "ordinary reason",
        )
        self.foreign_request = self.make_request(
            self.other, self.annual, "foreign reason",
        )
        self.client = APIClient()

    def make_request(self, employee, leave_type, reason):
        return LeaveRequest.objects.create(
            employee=employee,
            manager_snapshot=employee.manager,
            leave_type=leave_type,
            start_date=dt.date(2026, 6, 1),
            end_date=dt.date(2026, 6, 1),
            working_days=Decimal("1"),
            status="APPROVED",
            reason=reason,
        )

    def csv_text(self, response):
        return b"".join(response.streaming_content).decode("utf-8-sig")

    def test_export_route_is_registered(self):
        self.assertEqual(
            resolve("/api/v1/exports/leave-requests.csv").url_name,
            "exports",
        )

    def test_employee_can_export_own_data_but_not_another_employee(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.get("/api/v1/exports/leave-requests.csv?scope=me")
        self.assertEqual(response.status_code, 200)
        text = self.csv_text(response)
        self.assertIn("ordinary reason", text)
        self.assertNotIn("foreign reason", text)

        forbidden_target = self.client.get(
            f"/api/v1/exports/employees.csv?employee={self.other.pk}",
        )
        self.assertEqual(forbidden_target.status_code, 404)

    def test_manager_export_is_limited_to_direct_team(self):
        self.make_request(self.colleague, self.annual, "same-company non-team")
        self.client.force_authenticate(self.manager_user)
        response = self.client.get("/api/v1/exports/leave-requests.csv?scope=team")
        self.assertEqual(response.status_code, 200)
        text = self.csv_text(response)
        self.assertIn("ordinary reason", text)
        self.assertNotIn("same-company non-team", text)
        self.assertNotIn("foreign reason", text)

        team_directory = self.client.get("/api/v1/exports/employees.csv")
        self.assertEqual(team_directory.status_code, 200)
        directory_text = self.csv_text(team_directory)
        self.assertIn("EX-A-1", directory_text)
        self.assertNotIn("EX-A-M", directory_text)
        self.assertNotIn("EX-A-2", directory_text)

        outside_team = self.client.get(
            f"/api/v1/exports/employees.csv?scope=team&employee={self.colleague.pk}",
        )
        self.assertEqual(outside_team.status_code, 404)

    def test_scoped_hr_export_cannot_cross_company(self):
        self.client.force_authenticate(self.hr_user)
        response = self.client.get("/api/v1/exports/employees.csv")
        self.assertEqual(response.status_code, 200)
        text = self.csv_text(response)
        self.assertIn("EX-A-1", text)
        self.assertNotIn("EX-B-1", text)

        cross_company = self.client.get(
            f"/api/v1/exports/employee-balances.csv?year=1405&employee={self.other.pk}",
        )
        self.assertEqual(cross_company.status_code, 404)

    def test_employee_balance_export_matches_confidential_balance_visibility(self):
        create_entitlement(
            employee=self.employee, leave_type=self.annual, year=1405,
            base_days=Decimal("20"), actor=self.hr_user, reason="opening",
            idempotency_key="export-annual-opening",
        )
        create_entitlement(
            employee=self.employee, leave_type=self.confidential, year=1405,
            base_days=Decimal("4"), actor=self.hr_user, reason="opening",
            idempotency_key="export-confidential-opening",
        )
        self.client.force_authenticate(self.employee_user)
        own_export = self.client.get(
            "/api/v1/exports/employee-balances.csv?year=1405",
        )
        self.assertEqual(own_export.status_code, 200)
        own_text = self.csv_text(own_export)
        self.assertIn("export-annual", own_text)
        self.assertNotIn("export-medical", own_text)

        self.client.force_authenticate(self.hr_user)
        hr_export = self.client.get(
            f"/api/v1/exports/employee-balances.csv?year=1405&employee={self.employee.pk}",
        )
        self.assertEqual(hr_export.status_code, 200)
        self.assertIn("export-medical", self.csv_text(hr_export))

    def test_confidential_leave_is_redacted_before_csv_serialization(self):
        self.make_request(self.employee, self.confidential, "PRIVATE-REASON-CANARY")
        self.client.force_authenticate(self.manager_user)
        response = self.client.get("/api/v1/exports/leave-requests.csv?scope=team")
        self.assertEqual(response.status_code, 200)
        text = self.csv_text(response)
        self.assertIn("غایب", text)
        self.assertNotIn("CONFIDENTIAL-TYPE", text)
        self.assertNotIn("PRIVATE-REASON-CANARY", text)

    def test_csv_formula_injection_is_neutralized(self):
        self.employee_user.first_name = '=HYPERLINK("https://example.invalid")'
        self.employee_user.save(update_fields=["first_name"])
        self.client.force_authenticate(self.hr_user)
        response = self.client.get("/api/v1/exports/employees.csv")
        self.assertEqual(response.status_code, 200)
        text = self.csv_text(response)
        self.assertIn("'=HYPERLINK", text)

    def test_xlsx_content_type_and_formula_cells(self):
        self.employee_user.first_name = "=1+1"
        self.employee_user.save(update_fields=["first_name"])
        self.client.force_authenticate(self.hr_user)
        response = self.client.get("/api/v1/exports/employees.xlsx")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("no-store", response["Cache-Control"])
        workbook = load_workbook(io.BytesIO(response.content))
        worksheet = workbook.active
        string_values = [
            cell for row in worksheet.iter_rows() for cell in row
            if isinstance(cell.value, str)
        ]
        formula_like = next(cell for cell in string_values if cell.value.startswith("'=1+1"))
        self.assertNotEqual(formula_like.data_type, "f")
        self.assertEqual(workbook.properties.creator, "ZSH Leave")
        self.assertNotIn(self.hr_user.username, workbook.properties.creator)

    def test_executive_export_is_aggregate_and_respects_small_group_suppression(self):
        for index in range(3):
            user = get_user_model().objects.create_user(
                username=f"export-exec-employee-{index}",
            )
            EmployeeProfile.objects.create(
                user=user, company=self.company, department=self.department,
                personnel_code=f"EX-AGG-{index}", start_date=dt.date(2020, 1, 1),
            )
        executive = get_user_model().objects.create_user(username="export-exec")
        RoleAssignment.objects.create(
            user=executive, role=RoleAssignment.ROLE_EXEC,
            scope=RoleAssignment.SCOPE_COMPANY, company=self.company,
        )
        self.client.force_authenticate(executive)
        response = self.client.get("/api/v1/exports/absences.csv")
        self.assertEqual(response.status_code, 200)
        text = self.csv_text(response)
        self.assertEqual(next(csv.reader(io.StringIO(text))), ["label", "value"])
        self.assertNotIn("employeeId", text)
        self.assertNotIn("EX-A-1", text)
        self.assertNotIn("Annual leave", text)

    def test_bradford_export_uses_the_report_permission_and_configuration(self):
        executive = get_user_model().objects.create_user(username="export-bradford-exec")
        RoleAssignment.objects.create(
            user=executive, role=RoleAssignment.ROLE_EXEC,
            scope=RoleAssignment.SCOPE_COMPANY, company=self.company,
        )
        self.client.force_authenticate(executive)
        self.assertEqual(
            self.client.get("/api/v1/exports/bradford.xlsx").status_code,
            403,
        )

        self.client.force_authenticate(self.hr_user)
        report_response = self.client.get("/api/v1/reports/bradford")
        export_response = self.client.get("/api/v1/exports/bradford.csv")
        self.assertEqual(report_response.status_code, 409)
        self.assertEqual(export_response.status_code, report_response.status_code)

    def test_admin_can_export_global_employee_directory_but_not_leave_records(self):
        admin = get_user_model().objects.create_superuser(
            username="export-admin", email="export-admin@example.invalid", password="not-used",
        )
        self.client.force_authenticate(admin)
        response = self.client.get("/api/v1/exports/employees.csv")
        self.assertEqual(response.status_code, 200)
        text = self.csv_text(response)
        self.assertIn("EX-A-1", text)
        self.assertIn("EX-B-1", text)
        self.assertEqual(
            self.client.get("/api/v1/exports/leave-requests.csv").status_code,
            200,
        )
        self.assertEqual(self.csv_text(
            self.client.get("/api/v1/exports/leave-requests.csv"),
        ).count("foreign reason"), 0)

    def test_csv_export_streams_and_enforces_row_limit(self):
        self.client.force_authenticate(self.hr_user)
        with patch("leave.export_views.MAX_EXPORT_ROWS", 1):
            too_many = self.client.get("/api/v1/exports/employees.csv")
            self.assertEqual(too_many.status_code, 413)

        response = self.client.get("/api/v1/exports/employees.csv?employee=" + str(self.employee.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")

    def test_export_limits_date_ranges_and_rejects_unscoped_filters(self):
        self.client.force_authenticate(self.hr_user)
        invalid_range = self.client.get(
            "/api/v1/exports/leave-requests.csv?from=2025-01-01&to=2026-01-02",
        )
        self.assertEqual(invalid_range.status_code, 400)
        unscoped_filter = self.client.get(
            f"/api/v1/exports/employees.csv?company={self.other_company.pk}",
        )
        self.assertEqual(unscoped_filter.status_code, 400)

    def test_sensitive_export_audit_has_scope_correlation_and_no_row_contents(self):
        self.client.force_authenticate(self.hr_user)
        response = self.client.get(
            "/api/v1/exports/leave-requests.csv?status=APPROVED",
            HTTP_X_CORRELATION_ID="export-audit-1",
        )
        self.assertEqual(response.status_code, 200)
        audit = AuditEvent.objects.get(action="data.exported", entity="Export")
        self.assertEqual(audit.actor, self.hr_user)
        self.assertEqual(audit.entity_id, "leave-requests")
        self.assertEqual(audit.correlation_id, "export-audit-1")
        self.assertEqual(audit.after["rowCount"], 1)
        self.assertEqual(audit.after["filters"], {"status": "APPROVED"})
        self.assertEqual(audit.after["scope"]["type"], "hr_authorized_records")
        self.assertNotIn("ordinary reason", str(audit.after))
        self.assertIsNotNone(audit.created_at)

    def test_export_download_requires_authentication_and_is_not_persisted(self):
        response = self.client.get("/api/v1/exports/employees.csv")
        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(AuditEvent.objects.filter(action="data.exported").count(), 0)
        self.client.force_authenticate(self.employee_user)
        unavailable_file = self.client.get("/api/v1/exports/downloads/expired")
        self.assertEqual(unavailable_file.status_code, 404)
