import ipaddress
import importlib
import os
from unittest.mock import patch

from django.conf import settings
from django.test import Client, TestCase, override_settings


TRUSTED_PROXY_NETWORKS = (ipaddress.ip_network("10.42.0.0/16"),)
PRODUCTION_MIDDLEWARE = [
    "leave.middleware.TrustedProxySSLHeaderMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "leave.middleware.AuditContextMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


@override_settings(
    ALLOWED_HOSTS=["leave.example.test"],
    CSRF_TRUSTED_ORIGINS=["https://app.example.test"],
    CSRF_COOKIE_SECURE=True,
    SESSION_COOKIE_SECURE=True,
    SECURE_HSTS_SECONDS=31536000,
    SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    SECURE_SSL_REDIRECT=True,
    ZSH_TRUSTED_PROXY_NETWORKS=TRUSTED_PROXY_NETWORKS,
    MIDDLEWARE=PRODUCTION_MIDDLEWARE,
)
class ProductionProxySecurityTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True, raise_request_exception=False)
        self.host = "leave.example.test"
        self.proxy_addr = "10.42.0.8"

    def test_trusted_proxy_https_reaches_health_and_readiness_without_redirect(self):
        for path in ("/api/v1/health/", "/api/v1/ready/"):
            with self.subTest(path=path):
                response = self.client.get(
                    path,
                    HTTP_HOST=self.host,
                    HTTP_X_FORWARDED_PROTO="https",
                    REMOTE_ADDR=self.proxy_addr,
                )
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.get("Strict-Transport-Security"),
                                 "max-age=31536000; includeSubDomains")

    def test_untrusted_forwarded_https_is_ignored_and_http_redirects_once(self):
        response = self.client.get(
            "/api/v1/health/",
            HTTP_HOST=self.host,
            HTTP_X_FORWARDED_PROTO="https",
            REMOTE_ADDR="198.51.100.25",
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "https://leave.example.test/api/v1/health/")

        secure_response = self.client.get(
            response["Location"],
            secure=True,
            HTTP_HOST=self.host,
            HTTP_X_FORWARDED_PROTO="https",
            REMOTE_ADDR=self.proxy_addr,
        )
        self.assertEqual(secure_response.status_code, 200)

    def test_trusted_proxy_http_is_redirected_and_does_not_loop_for_https(self):
        redirect = self.client.get(
            "/api/v1/health/",
            HTTP_HOST=self.host,
            HTTP_X_FORWARDED_PROTO="http",
            REMOTE_ADDR=self.proxy_addr,
        )
        self.assertEqual(redirect.status_code, 301)

        final_response = self.client.get(
            redirect["Location"],
            HTTP_HOST=self.host,
            HTTP_X_FORWARDED_PROTO="https",
            REMOTE_ADDR=self.proxy_addr,
        )
        self.assertEqual(final_response.status_code, 200)

    def test_multi_value_forwarded_proto_is_not_accepted(self):
        response = self.client.get(
            "/api/v1/health/",
            HTTP_HOST=self.host,
            HTTP_X_FORWARDED_PROTO="https, http",
            REMOTE_ADDR=self.proxy_addr,
        )
        self.assertEqual(response.status_code, 301)

    def test_direct_https_remains_secure_without_trusting_forwarded_headers(self):
        response = self.client.get(
            "/api/v1/health/",
            secure=True,
            HTTP_HOST=self.host,
            HTTP_X_FORWARDED_PROTO="http",
            REMOTE_ADDR="198.51.100.25",
        )
        self.assertEqual(response.status_code, 200)

    def test_unconfigured_hosts_are_rejected(self):
        response = self.client.get(
            "/api/v1/health/",
            secure=True,
            HTTP_HOST="attacker.example",
        )
        self.assertEqual(response.status_code, 400)

    def test_csrf_trusted_origin_and_secure_session_cookies(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="proxy-login",
            password="Secure-Test-Password-123!",
        )
        csrf_bootstrap = self.client.get(
            "/api/v1/auth/me",
            secure=True,
            HTTP_HOST=self.host,
            HTTP_X_FORWARDED_PROTO="https",
            REMOTE_ADDR=self.proxy_addr,
        )
        self.assertEqual(csrf_bootstrap.status_code, 401)
        csrf_cookie = csrf_bootstrap.cookies["csrftoken"]
        self.assertTrue(csrf_cookie["secure"])

        rejected = self.client.post(
            "/api/v1/auth/login",
            data={"username": user.username, "password": "Secure-Test-Password-123!"},
            content_type="application/json",
            secure=True,
            HTTP_HOST=self.host,
            HTTP_ORIGIN="https://attacker.example",
            HTTP_X_CSRFTOKEN=csrf_cookie.value,
            HTTP_X_FORWARDED_PROTO="https",
            REMOTE_ADDR=self.proxy_addr,
        )
        self.assertEqual(rejected.status_code, 403)

        accepted = self.client.post(
            "/api/v1/auth/login",
            data={"username": user.username, "password": "Secure-Test-Password-123!"},
            content_type="application/json",
            secure=True,
            HTTP_HOST=self.host,
            HTTP_ORIGIN="https://app.example.test",
            HTTP_X_CSRFTOKEN=csrf_cookie.value,
            HTTP_X_FORWARDED_PROTO="https",
            REMOTE_ADDR=self.proxy_addr,
        )
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertTrue(accepted.cookies["sessionid"]["secure"])
        self.assertTrue(accepted.cookies["csrftoken"]["secure"])


class ProductionSettingsValidationTests(TestCase):
    def test_production_settings_enable_proxy_security_and_reject_http_csrf_origins(self):
        environment = {
            "ZSH_SECRET_KEY": "x" * 50,
            "ZSH_ALLOWED_HOSTS": "leave.example.test",
            "ZSH_DB_USER": "zsh_app",
            "ZSH_DB_PASSWORD": "safe-test-password",
            "ZSH_ATTACHMENT_ROOT": "/tmp/zsh-attachment-validation",
            "ZSH_CSRF_TRUSTED_ORIGINS": "https://app.example.test",
            "ZSH_TRUSTED_PROXY_IPS": "10.42.0.0/16",
        }
        settings_base = importlib.import_module("config.settings_base")
        with patch.dict(os.environ, environment, clear=True):
            importlib.reload(settings_base)
            settings_prod = importlib.reload(
                importlib.import_module("config.settings_prod"),
            )

            self.assertFalse(settings_prod.DEBUG)
            self.assertTrue(settings_prod.SECURE_SSL_REDIRECT)
            self.assertTrue(settings_prod.SESSION_COOKIE_SECURE)
            self.assertTrue(settings_prod.CSRF_COOKIE_SECURE)
            self.assertEqual(settings_prod.SECURE_HSTS_SECONDS, 31536000)
            self.assertTrue(settings_prod.SECURE_HSTS_INCLUDE_SUBDOMAINS)
            self.assertEqual(settings_prod.ALLOWED_HOSTS, ["leave.example.test"])
            self.assertEqual(
                settings_prod.SECURE_PROXY_SSL_HEADER,
                ("HTTP_X_FORWARDED_PROTO", "https"),
            )
            self.assertEqual(
                tuple(str(network) for network in settings_prod.ZSH_TRUSTED_PROXY_NETWORKS),
                ("10.42.0.0/16",),
            )
            self.assertIn("https://app.example.test", settings_prod.CSRF_TRUSTED_ORIGINS)

        with patch.dict(os.environ, {
            **environment,
            "ZSH_CSRF_TRUSTED_ORIGINS": "http://app.example.test",
        }, clear=True):
            importlib.reload(settings_base)
            with self.assertRaisesRegex(RuntimeError, "exact HTTPS origins"):
                importlib.reload(settings_prod)
        with patch.dict(os.environ, {
            **environment,
            "ZSH_CSRF_TRUSTED_ORIGINS": "https://*",
        }, clear=True):
            importlib.reload(settings_base)
            with self.assertRaisesRegex(RuntimeError, "exact HTTPS origins"):
                importlib.reload(settings_prod)
        importlib.reload(settings_base)

    def test_production_settings_reject_wildcard_hosts(self):
        environment = {
            "ZSH_SECRET_KEY": "x" * 50,
            "ZSH_ALLOWED_HOSTS": "*",
            "ZSH_DB_USER": "zsh_app",
            "ZSH_DB_PASSWORD": "safe-test-password",
            "ZSH_ATTACHMENT_ROOT": "/tmp/zsh-attachment-validation",
        }
        settings_base = importlib.import_module("config.settings_base")
        with patch.dict(os.environ, environment, clear=True):
            importlib.reload(settings_base)
            with self.assertRaisesRegex(RuntimeError, "Wildcard hosts"):
                importlib.reload(importlib.import_module("config.settings_prod"))
        importlib.reload(settings_base)

    def test_production_settings_reject_attachment_storage_inside_repository(self):
        environment = {
            "ZSH_SECRET_KEY": "x" * 50,
            "ZSH_ALLOWED_HOSTS": "leave.example.test",
            "ZSH_DB_USER": "zsh_app",
            "ZSH_DB_PASSWORD": "safe-test-password",
            "ZSH_ATTACHMENT_ROOT": str(settings.PROJECT_ROOT / "private-attachments"),
        }
        settings_base = importlib.import_module("config.settings_base")
        with patch.dict(os.environ, environment, clear=True):
            importlib.reload(settings_base)
            with self.assertRaisesRegex(RuntimeError, "outside the application repository"):
                importlib.reload(importlib.import_module("config.settings_prod"))
        importlib.reload(settings_base)

    def test_test_settings_remain_separate_from_production_ssl_redirect(self):
        self.assertFalse(settings.SECURE_SSL_REDIRECT)
        self.assertIsNone(settings.SECURE_PROXY_SSL_HEADER)
