import datetime as dt
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from leave.entitlement_services import create_entitlement
from leave.models import (
    Company,
    EntitlementEvent,
    EmployeeProfile,
    LeaveEntitlement,
    LeaveType,
    RoleAssignment,
)

HEADER = "personnel_code,type,year,days\n"


class EntitlementImportApiTests(TestCase):
    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.company = Company.objects.create(code="IMPORT", name="Import company")
        self.hr_user = user_model.objects.create_user(username="import-hr")
        RoleAssignment.objects.create(
            user=self.hr_user,
            role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY,
            company=self.company,
        )
        self.employee = self.make_employee("IMPORT-1")
        self.second_employee = self.make_employee("IMPORT-2")
        self.annual = LeaveType.objects.create(
            key="import-annual", label_fa="سالانه", counts_against_balance=True,
        )
        self.sick = LeaveType.objects.create(
            key="import-sick", label_fa="استعلاجی", counts_against_balance=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.hr_user)

    def make_employee(self, personnel_code):
        return EmployeeProfile.objects.create(
            user=get_user_model().objects.create_user(username=personnel_code),
            company=self.company,
            personnel_code=personnel_code,
            start_date=dt.date(2020, 1, 1),
        )

    def post_import(self, csv_text, *, preview=False):
        cache.clear()
        path = "/api/v1/entitlements/import/"
        if preview:
            path += "?dry_run=1"
        return self.client.post(path, {"csv": csv_text}, format="json")

    def test_duplicate_business_key_inside_file_rejects_all_rows(self):
        csv_text = (
            HEADER
            + f"{self.employee.personnel_code},{self.annual.key},1405,10\n"
            + f"{self.employee.personnel_code},{self.annual.key},1405,12\n"
        )

        preview = self.post_import(csv_text, preview=True).json()
        committed = self.post_import(csv_text).json()

        for result in (preview, committed):
            self.assertEqual((result["accepted"], result["rejected"]), (1, 1))
            self.assertEqual(result["rows"][1]["line"], 3)
            self.assertEqual(result["rows"][1]["errorCode"], "duplicate_in_file")
        self.assertEqual(LeaveEntitlement.objects.count(), 0)
        self.assertEqual(EntitlementEvent.objects.count(), 0)

    def test_duplicate_business_key_already_in_database_is_rejected(self):
        create_entitlement(
            employee=self.employee,
            leave_type=self.annual,
            year=1405,
            base_days=Decimal("10"),
            actor=self.hr_user,
            reason="existing allocation",
            idempotency_key="import-existing",
        )
        before_count = LeaveEntitlement.objects.count()
        response = self.post_import(
            f"{HEADER}{self.employee.personnel_code},{self.annual.key},1405,10\n",
            preview=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rows"][0]["errorCode"], "duplicate_existing")
        self.assertEqual(LeaveEntitlement.objects.count(), before_count)

    def test_different_employee_or_leave_type_is_not_a_duplicate(self):
        csv_text = (
            HEADER
            + f"{self.employee.personnel_code},{self.annual.key},1405,10\n"
            + f"{self.employee.personnel_code},{self.sick.key},1405,8\n"
            + f"{self.second_employee.personnel_code},{self.annual.key},1405,12\n"
        )

        response = self.post_import(csv_text)

        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()["accepted"], response.json()["rejected"]), (3, 0))
        self.assertEqual(LeaveEntitlement.objects.count(), 3)

    def test_invalid_references_return_scoped_actionable_codes(self):
        csv_text = (
            HEADER
            + "NOT-IN-SCOPE,import-annual,1405,10\n"
            + f"{self.employee.personnel_code},missing-type,1405,10\n"
        )

        response = self.post_import(csv_text, preview=True)

        self.assertEqual(response.json()["rows"][0]["errorCode"], "invalid_employee")
        self.assertEqual(response.json()["rows"][0]["employee"], "")
        self.assertEqual(response.json()["rows"][1]["errorCode"], "invalid_leave_type")

    def test_headers_numbers_and_empty_input_have_specific_errors(self):
        cases = (
            ("personnel_code,type\n", "missing_header"),
            (HEADER.replace("days", "days,extra") + "IMPORT-1,import-annual,1405,10,x\n",
             "extra_header"),
            (f"{HEADER}IMPORT-1,import-annual,1405,1e2\n", "invalid_days"),
            (f"{HEADER}IMPORT-1,import-annual,14_05,10\n", "invalid_year"),
            ("", "empty_file"),
            (HEADER, "empty_file"),
        )
        for csv_text, error_code in cases:
            with self.subTest(error_code=error_code, csv_text=csv_text):
                response = self.post_import(csv_text, preview=True)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["rejected"], 1)
                self.assertEqual(response.json()["rows"][0]["errorCode"], error_code)

    def test_utf8_bom_whitespace_and_persian_digits_are_supported(self):
        csv_text = (
            "\ufeff personnel_code , type , year , days \n"
            " IMPORT-1 , import-annual , ۱۴۰۵ , ۱۰٫۵ \n"
        )

        response = self.post_import(csv_text, preview=True)

        self.assertEqual(response.json()["accepted"], 1)
        self.assertEqual(response.json()["rows"][0]["year"], 1405)
        self.assertEqual(response.json()["rows"][0]["days"], "10.5")

    def test_preview_and_commit_share_validation_and_commit_rechecks_database(self):
        csv_text = f"{HEADER}IMPORT-1,import-annual,1406,10\n"
        preview = self.post_import(csv_text, preview=True).json()
        self.assertEqual((preview["accepted"], preview["rejected"]), (1, 0))

        create_entitlement(
            employee=self.employee,
            leave_type=self.annual,
            year=1406,
            base_days=Decimal("10"),
            actor=self.hr_user,
            reason="created after preview",
            idempotency_key="import-stale-preview",
        )
        commit = self.post_import(csv_text).json()

        self.assertEqual((commit["accepted"], commit["rejected"]), (0, 1))
        self.assertEqual(commit["rows"][0]["errorCode"], "duplicate_existing")
        self.assertEqual(
            LeaveEntitlement.objects.filter(employee=self.employee, year=1406).count(),
            1,
        )

    def test_invalid_row_prevents_all_valid_rows_from_being_committed(self):
        csv_text = (
            HEADER
            + "IMPORT-1,import-annual,1405,10\n"
            + "UNKNOWN,import-sick,1405,8\n"
        )
        event_count = EntitlementEvent.objects.count()

        preview = self.post_import(csv_text, preview=True).json()
        commit = self.post_import(csv_text).json()

        self.assertEqual((preview["accepted"], preview["rejected"]), (1, 1))
        self.assertEqual((commit["accepted"], commit["rejected"]), (1, 1))
        self.assertEqual(commit["rows"][1]["errorCode"], "invalid_employee")
        self.assertEqual(LeaveEntitlement.objects.count(), 0)
        self.assertEqual(EntitlementEvent.objects.count(), event_count)

    def test_commit_rolls_back_prior_rows_if_ledger_creation_fails(self):
        from unittest.mock import patch

        from leave import frontend_api_views
        from leave.entitlement_services import EntitlementLedgerError

        csv_text = (
            HEADER
            + "IMPORT-1,import-annual,1405,10\n"
            + "IMPORT-2,import-sick,1405,8\n"
        )
        original_create = frontend_api_views.create_entitlement_for_import
        calls = 0

        def create_then_fail(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise EntitlementLedgerError("simulated ledger failure")
            return original_create(**kwargs)

        with patch(
            "leave.frontend_api_views.create_entitlement_for_import",
            side_effect=create_then_fail,
        ):
            response = self.post_import(csv_text)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(LeaveEntitlement.objects.count(), 0)
        self.assertEqual(EntitlementEvent.objects.count(), 0)


class ConcurrentEntitlementImportTests(TransactionTestCase):
    reset_sequences = True

    @skipUnless(connection.vendor == "postgresql", "Import row locking requires PostgreSQL.")
    def test_concurrent_duplicate_imports_commit_at_most_once(self):
        cache.clear()
        user_model = get_user_model()
        company = Company.objects.create(code="IMPORT-RACE", name="Import race")
        operator = user_model.objects.create_user(username="import-race-hr")
        RoleAssignment.objects.create(
            user=operator,
            role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY,
            company=company,
        )
        employee = EmployeeProfile.objects.create(
            user=user_model.objects.create_user(username="import-race-employee"),
            company=company,
            personnel_code="IMPORT-RACE-1",
            start_date=dt.date(2020, 1, 1),
        )
        leave_type = LeaveType.objects.create(
            key="import-race-type", label_fa="آزمون هم‌زمان",
        )
        csv_text = f"{HEADER}{employee.personnel_code},{leave_type.key},1405,10\n"
        barrier = threading.Barrier(2)

        def submit_import():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(user=operator)
                barrier.wait(timeout=10)
                response = client.post(
                    "/api/v1/entitlements/import/",
                    {"csv": csv_text},
                    format="json",
                )
                return response.status_code, response.json()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: submit_import(), range(2)))

        self.assertEqual(
            LeaveEntitlement.objects.filter(employee=employee, leave_type=leave_type).count(),
            1,
        )
        self.assertEqual(
            sum(result.get("accepted", 0) for _status, result in results),
            1,
        )
