import datetime as dt
import ipaddress
import tempfile
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.throttling import SimpleRateThrottle

from leave.models import (
    Company,
    Department,
    EmployeeProfile,
    LeaveRequest,
    LeaveType,
    RoleAssignment,
)
from leave.throttling import ScopedClientThrottle, ScopedUserThrottle, trusted_client_ip

User = get_user_model()


class RateLimitingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="throttle-user", password="unused")
        self.client = APIClient()

    def test_anonymous_requests_are_limited_with_consistent_429_and_retry_after(self):
        first_client = APIClient()
        second_client = APIClient()
        first_client.defaults["REMOTE_ADDR"] = "198.51.100.10"
        second_client.defaults["REMOTE_ADDR"] = "198.51.100.10"

        for index in range(20):
            client = first_client if index % 2 == 0 else second_client
            response = client.get("/api/v1/auth/me")
            self.assertEqual(response.status_code, 401)

        response = second_client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "rate_limited")
        self.assertEqual(response.json()["detail"], "Request was throttled.")
        self.assertEqual(response.json()["retry_after"], int(response["Retry-After"]))
        self.assertGreaterEqual(int(response["Retry-After"]), 1)

    def test_authenticated_limit_tracks_both_user_and_client(self):
        other_user = User.objects.create_user(username="other-throttle-user", password="unused")
        client = APIClient()
        client.force_authenticate(self.user)
        with patch.dict(SimpleRateThrottle.THROTTLE_RATES, {
            "user": "2/min",
            "authenticated_client": "10/min",
        }):
            for _ in range(2):
                self.assertEqual(client.get("/api/v1/auth/me").status_code, 200)
            self.assertEqual(client.get("/api/v1/auth/me").status_code, 429)

        cache.clear()
        client.force_authenticate(self.user)
        shared_ip_client = APIClient()
        shared_ip_client.force_authenticate(other_user)
        client.defaults["REMOTE_ADDR"] = "198.51.100.11"
        shared_ip_client.defaults["REMOTE_ADDR"] = "198.51.100.11"
        with patch.dict(SimpleRateThrottle.THROTTLE_RATES, {
            "user": "10/min",
            "authenticated_client": "1/min",
        }):
            self.assertEqual(client.get("/api/v1/auth/me").status_code, 200)
            self.assertEqual(shared_ip_client.get("/api/v1/auth/me").status_code, 429)

    def test_login_limit_cannot_be_bypassed_by_spoofing_forwarded_for(self):
        client = APIClient(enforce_csrf_checks=True)
        client.defaults["REMOTE_ADDR"] = "198.51.100.12"
        csrf = client.get("/api/v1/auth/me").cookies["csrftoken"].value
        payload = {"username": "not-an-account", "password": "not-a-password"}

        for index in range(5):
            response = client.post(
                "/api/v1/auth/login",
                payload,
                format="json",
                HTTP_X_CSRFTOKEN=csrf,
                HTTP_X_FORWARDED_FOR=f"192.0.2.{index + 1}",
            )
            self.assertEqual(response.status_code, 401)
        with self.assertLogs("leave.security", level="WARNING") as captured:
            response = client.post(
                "/api/v1/auth/login",
                payload,
                format="json",
                HTTP_X_CSRFTOKEN=csrf,
                HTTP_X_FORWARDED_FOR="203.0.113.99",
            )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "rate_limited")
        self.assertEqual(response["Retry-After"], response.json()["retry_after"].__str__())
        self.assertIn("event=rate_limit_exceeded", "\n".join(captured.output))
        self.assertNotIn("not-a-password", "\n".join(captured.output))
        self.assertNotIn("not-an-account", "\n".join(captured.output))

    def test_login_account_limit_is_independent_of_account_existence(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get("/api/v1/auth/me").cookies["csrftoken"].value
        outcomes = []
        for username in ("throttle-user", "account-that-does-not-exist"):
            cache.clear()
            client.defaults["REMOTE_ADDR"] = "198.51.100.100"
            for attempt in range(6):
                client.defaults["REMOTE_ADDR"] = f"198.51.100.{100 + attempt}"
                response = client.post(
                    "/api/v1/auth/login",
                    {"username": username, "password": "wrong-password"},
                    format="json",
                    HTTP_X_CSRFTOKEN=csrf,
                )
                if attempt < 5:
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.json()["code"], "invalid_credentials")
                else:
                    self.assertEqual(response.status_code, 429)
                    outcomes.append(response.json())
        self.assertEqual(outcomes[0], outcomes[1])

    def test_activation_has_a_dedicated_limit(self):
        payload = {
            "token": "invalid",
            "email": "activation@example.test",
            "password": "Unused-Password-12345!",
        }
        client = APIClient()
        for _ in range(5):
            self.assertEqual(
                client.post("/api/v1/auth/activate", payload, format="json").status_code,
                400,
            )
        response = client.post("/api/v1/auth/activate", payload, format="json")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "rate_limited")

    def test_forwarded_for_is_used_only_when_remote_address_is_trusted(self):
        request = APIRequestFactory().get(
            "/",
            HTTP_X_FORWARDED_FOR="203.0.113.7, 10.1.0.2",
            REMOTE_ADDR="198.51.100.20",
        )
        with override_settings(
            ZSH_TRUSTED_PROXY_NETWORKS=(ipaddress.ip_network("10.0.0.0/8"),),
        ):
            self.assertEqual(trusted_client_ip(request), "198.51.100.20")

        trusted_request = APIRequestFactory().get(
            "/",
            HTTP_X_FORWARDED_FOR="203.0.113.7, 10.1.0.2",
            REMOTE_ADDR="10.1.0.3",
        )
        with override_settings(
            ZSH_TRUSTED_PROXY_NETWORKS=(ipaddress.ip_network("10.0.0.0/8"),),
        ):
            self.assertEqual(trusted_client_ip(trusted_request), "203.0.113.7")

    def test_password_operation_has_a_dedicated_limit(self):
        self.client.force_authenticate(self.user)
        payload = {"current": "wrong", "next": "Valid-Password-12345!"}

        for _ in range(5):
            self.assertEqual(
                self.client.post("/api/v1/auth/password", payload, format="json").status_code,
                400,
            )
        response = self.client.post("/api/v1/auth/password", payload, format="json")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "rate_limited")

    def test_invitation_resend_has_a_dedicated_limit(self):
        company = Company.objects.create(code="THROTTLE", name="Throttle company")
        department = Department.objects.create(
            company=company,
            code="OPS",
            name="Operations",
        )
        employee_user = User.objects.create_user(username="throttle-employee", password="unused")
        employee = EmployeeProfile.objects.create(
            user=employee_user,
            company=company,
            department=department,
            personnel_code="THROTTLE-1",
            start_date="2020-01-01",
        )
        RoleAssignment.objects.create(
            user=self.user,
            role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY,
            company=company,
        )
        self.client.force_authenticate(self.user)
        result = SimpleNamespace(status="sent", development_url=None)

        with patch("leave.invitation_views.invite_employee", return_value=result):
            for _ in range(10):
                self.assertEqual(
                    self.client.post(
                        f"/api/v1/employees/{employee.pk}/invitation/",
                        {},
                        format="json",
                    ).status_code,
                    200,
                )
            response = self.client.post(
                f"/api/v1/employees/{employee.pk}/invitation/",
                {},
                format="json",
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "rate_limited")

    def test_bulk_import_limit_is_applied_before_import_processing(self):
        self.client.force_authenticate(self.user)
        payload = {"csv": "personnel_code,leave_type_key,year,base_days\n"}
        for _ in range(5):
            self.assertEqual(
                self.client.post(
                    "/api/v1/entitlements/import/",
                    payload,
                    format="json",
                ).status_code,
                403,
            )
        response = self.client.post(
            "/api/v1/entitlements/import/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "rate_limited")

    def test_reports_have_a_dedicated_expensive_operation_limit(self):
        self.client.force_authenticate(self.user)
        for _ in range(10):
            self.assertEqual(
                self.client.get("/api/v1/reports/absences").status_code,
                403,
            )
        response = self.client.get("/api/v1/reports/absences")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "rate_limited")

    def test_password_reset_scope_enforces_its_policy_for_scoped_views(self):
        request = APIRequestFactory().get("/", REMOTE_ADDR="198.51.100.40")
        request.user = self.user
        view = SimpleNamespace(throttle_scope="password_reset")
        client_throttle = ScopedClientThrottle()
        user_throttle = ScopedUserThrottle()

        with patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"password_reset": "2/min"}):
            self.assertTrue(client_throttle.allow_request(request, view))
            self.assertTrue(user_throttle.allow_request(request, view))
            self.assertTrue(client_throttle.allow_request(request, view))
            self.assertTrue(user_throttle.allow_request(request, view))
            self.assertFalse(client_throttle.allow_request(request, view))
            self.assertFalse(user_throttle.allow_request(request, view))

    def test_employee_search_and_file_upload_have_operation_scopes(self):
        self.client.force_authenticate(self.user)
        with patch.dict(SimpleRateThrottle.THROTTLE_RATES, {
            "employee_search": "2/min",
        }):
            for _ in range(2):
                self.assertEqual(self.client.get("/api/v1/employees/?q=staff").status_code, 200)
            self.assertEqual(self.client.get("/api/v1/employees/?q=staff").status_code, 429)

        cache.clear()
        company = Company.objects.create(code="UPLOAD", name="Upload company")
        department = Department.objects.create(
            company=company,
            code="OPS",
            name="Operations",
        )
        employee = EmployeeProfile.objects.create(
            user=self.user,
            company=company,
            department=department,
            personnel_code="UPLOAD-1",
            start_date=dt.date(2020, 1, 1),
        )
        leave_type = LeaveType.objects.create(
            key="throttle-annual",
            label_fa="Annual",
            counts_against_balance=True,
        )
        leave_request = LeaveRequest.objects.create(
            employee=employee,
            leave_type=leave_type,
            start_date=dt.date(2026, 11, 2),
            end_date=dt.date(2026, 11, 2),
            working_days=Decimal("1"),
            status="PENDING",
        )
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                with patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"file_upload": "2/min"}):
                    for _ in range(2):
                        upload = SimpleUploadedFile(
                            "evidence.pdf",
                            b"%PDF-1.7\nrate limit test",
                            content_type="application/pdf",
                        )
                        self.assertEqual(
                            self.client.post(
                                f"/api/v1/leave-requests/{leave_request.pk}/attachments/",
                                {"file": upload},
                                format="multipart",
                            ).status_code,
                            201,
                        )
                    upload = SimpleUploadedFile(
                        "evidence.pdf",
                        b"%PDF-1.7\nrate limit test",
                        content_type="application/pdf",
                    )
                    response = self.client.post(
                        f"/api/v1/leave-requests/{leave_request.pk}/attachments/",
                        {"file": upload},
                        format="multipart",
                    )
        self.assertEqual(response.status_code, 429)

    def test_cache_counters_are_shared_by_separate_api_clients(self):
        first_client = APIClient()
        second_client = APIClient()
        first_client.defaults["REMOTE_ADDR"] = "198.51.100.41"
        second_client.defaults["REMOTE_ADDR"] = "198.51.100.41"

        for _ in range(20):
            self.assertEqual(first_client.get("/api/v1/auth/me").status_code, 401)
        response = second_client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 429)
