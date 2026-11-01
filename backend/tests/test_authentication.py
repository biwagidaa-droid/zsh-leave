import os
import importlib
from unittest.mock import patch

os.environ.setdefault("ZSH_ENV", "testing")
os.environ.setdefault("ZSH_SECRET_KEY", "test-secret-key")

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from leave.models import AuditEvent, Company, Department, EmployeeProfile, RoleAssignment

User = get_user_model()
OLD_PASSWORD = "Old-Secret-Long-123!"
NEW_PASSWORD = "Better-Secret-Long-456!"


class AuthenticationApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            username="staff",
            password=OLD_PASSWORD,
            first_name="Test",
            last_name="Staff",
            email="staff@example.test",
        )
        self.company = Company.objects.create(code="AUTH", name="Auth Company")
        self.department = Department.objects.create(company=self.company, code="OPS", name="Operations")
        self.profile = EmployeeProfile.objects.create(
            user=self.user,
            company=self.company,
            department=self.department,
            personnel_code="A-100",
            start_date="2020-01-01",
        )

    def csrf_token(self):
        response = self.client.get("/api/v1/auth/me")
        self.assertIn(response.status_code, (200, 401))
        self.assertIn("csrftoken", self.client.cookies)
        return self.client.cookies["csrftoken"].value

    def post_with_csrf(self, path, data=None):
        return self.client.post(
            path,
            data,
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

    def test_auth_me_bootstraps_csrf_cookie_and_requires_a_session(self):
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "unauthenticated")
        self.assertIn("csrftoken", response.cookies)

    def test_login_rotates_anonymous_session_and_returns_frontend_user_shape(self):
        anonymous_session = self.client.session
        anonymous_session["pre_login_state"] = "preserved"
        anonymous_session.save()
        token = self.csrf_token()
        anonymous_session_key = self.client.session.session_key
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "staff", "password": OLD_PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(self.client.session.session_key, anonymous_session_key)
        self.assertEqual(self.client.session["pre_login_state"], "preserved")
        self.assertEqual(
            response.json(),
            {
                "id": self.user.pk,
                "username": "staff",
                "displayName": "Test Staff",
                "email": "staff@example.test",
                "roles": ["employee"],
                "employeeId": self.profile.pk,
                "companyId": self.company.pk,
                "companyName": "Auth Company",
                "departmentName": "Operations",
                "personnelCode": "A-100",
                "managerName": None,
                "isEmployee": True,
            },
        )
        self.assertNotEqual(response.cookies["csrftoken"].value, token)
        self.assertEqual(self.client.get("/api/v1/auth/me").json(), response.json())
        self.assertEqual(self.client.session.get_expiry_age(), 8 * 60 * 60)

    def test_login_requires_csrf_and_never_accepts_inactive_accounts(self):
        missing_csrf = self.client.post(
            "/api/v1/auth/login",
            {"username": "staff", "password": OLD_PASSWORD},
            format="json",
        )
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(missing_csrf.json()["code"], "csrf_failed")

        token = self.csrf_token()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "staff", "password": OLD_PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "invalid_credentials")

    def test_invalid_login_uses_generic_message_and_missing_fields_are_rejected(self):
        response = self.post_with_csrf(
            "/api/v1/auth/login",
            {"username": "staff", "password": "not-the-password"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "invalid_credentials")
        self.assertNotIn("staff", response.content.decode())
        audit = AuditEvent.objects.get(action="auth.login.failed")
        self.assertEqual(audit.entity_id, "staff")
        self.assertNotIn("not-the-password", str(audit))

        response = self.post_with_csrf("/api/v1/auth/login", {"username": "staff"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("fields", response.json())

    def test_login_is_rate_limited(self):
        token = self.csrf_token()
        payload = {"username": "staff", "password": "incorrect"}
        for _ in range(5):
            response = self.client.post(
                "/api/v1/auth/login",
                payload,
                format="json",
                HTTP_X_CSRFTOKEN=token,
            )
            self.assertEqual(response.status_code, 401)
        response = self.client.post(
            "/api/v1/auth/login",
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 429)

    def test_logout_invalidates_session_and_requires_csrf(self):
        self.client.force_login(self.user)
        response = self.client.post("/api/v1/auth/logout", {}, format="json")
        self.assertEqual(response.status_code, 403)

        token = self.csrf_token()
        response = self.client.post(
            "/api/v1/auth/logout",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 204)
        self.assertTrue(AuditEvent.objects.filter(action="auth.logout", actor=self.user).exists())
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_password_change_validates_current_password_and_preserves_session(self):
        self.client.force_login(self.user)
        missing_csrf = self.client.post(
            "/api/v1/auth/password",
            {"current": OLD_PASSWORD, "next": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(missing_csrf.status_code, 403)
        token = self.csrf_token()
        response = self.client.post(
            "/api/v1/auth/password",
            {"current": "wrong", "next": NEW_PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_current_password")

        response = self.client.post(
            "/api/v1/auth/password",
            {"current": OLD_PASSWORD, "next": "short"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("next", response.json()["fields"])

        response = self.client.post(
            "/api/v1/auth/password",
            {"current": OLD_PASSWORD, "next": NEW_PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 204)
        self.assertTrue(
            AuditEvent.objects.filter(action="auth.password.changed", actor=self.user).exists()
        )
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 200)
        self.assertTrue(authenticate(username="staff", password=NEW_PASSWORD))
        self.assertFalse(authenticate(username="staff", password=OLD_PASSWORD))

    def test_new_passwords_use_argon2_and_legacy_passwords_upgrade(self):
        self.assertTrue(self.user.password.startswith("argon2$"))
        legacy = User.objects.create_user(username="legacy", password=None)
        legacy.password = make_password(OLD_PASSWORD, hasher="pbkdf2_sha256")
        legacy.save(update_fields=["password"])

        authenticated = authenticate(username="legacy", password=OLD_PASSWORD)
        self.assertEqual(authenticated.pk, legacy.pk)
        legacy.refresh_from_db()
        self.assertTrue(legacy.password.startswith("argon2$"))

    def test_frontend_role_metadata_uses_role_assignments_and_reporting_data(self):
        RoleAssignment.objects.create(
            user=self.user, role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY, company=self.company,
        )
        manager = User.objects.create_user(username="manager", password=OLD_PASSWORD)
        EmployeeProfile.objects.create(
            user=manager,
            company=self.company,
            personnel_code="A-200",
            start_date="2020-01-01",
        )
        self.profile.manager = EmployeeProfile.objects.get(user=manager)
        self.profile.save(update_fields=["manager"])
        response = self.post_with_csrf(
            "/api/v1/auth/login",
            {"username": "staff", "password": OLD_PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["roles"], ["hr", "employee"])
        self.assertEqual(response.json()["managerName"], "manager")


class ProductionAuthenticationSettingsTests(TestCase):
    def test_production_requires_secret_and_hosts(self):
        valid_environment = {
            "ZSH_SECRET_KEY": "x" * 50,
            "ZSH_ALLOWED_HOSTS": "example.test",
            "ZSH_DB_PASSWORD": "safe-test-password",
        }
        with patch.dict(os.environ, valid_environment, clear=True):
            settings_prod = importlib.import_module("config.settings_prod")
        self.assertFalse(settings_prod.DEBUG)
        self.assertTrue(settings_prod.SESSION_COOKIE_SECURE)
        self.assertTrue(settings_prod.CSRF_COOKIE_SECURE)
        self.assertTrue(settings_prod.SECURE_SSL_REDIRECT)
        with patch.dict(os.environ, {
            "ZSH_SECRET_KEY": "x" * 50,
            "ZSH_DB_PASSWORD": "safe-test-password",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ZSH_ALLOWED_HOSTS"):
                importlib.reload(settings_prod)
        with patch.dict(os.environ, {
            "ZSH_SECRET_KEY": "x" * 49,
            "ZSH_ALLOWED_HOSTS": "example.test",
            "ZSH_DB_PASSWORD": "safe-test-password",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "50 characters"):
                importlib.reload(settings_prod)
        with patch.dict(os.environ, {
            "ZSH_ALLOWED_HOSTS": "example.test",
            "ZSH_DB_PASSWORD": "safe-test-password",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ZSH_SECRET_KEY"):
                importlib.reload(settings_prod)
        with patch.dict(os.environ, {
            "ZSH_SECRET_KEY": "x" * 50,
            "ZSH_ALLOWED_HOSTS": "example.test",
            "ZSH_DB_PASSWORD": "safe-test-password",
            "ZSH_INVITATION_EXPOSE_DEV_LINKS": "1",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "cannot be exposed"):
                importlib.reload(settings_prod)
