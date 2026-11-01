import os
import unittest

from django.test import Client

os.environ.setdefault("ZSH_ENV", "testing")
os.environ.setdefault("ZSH_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ZSH_DEBUG", "1")
os.environ.setdefault("ZSH_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("ZSH_DB_NAME", "zsh_test")
os.environ.setdefault("ZSH_DB_USER", "postgres")
os.environ.setdefault("ZSH_DB_PASSWORD", "postgres")
os.environ.setdefault("ZSH_DB_HOST", "localhost")
os.environ.setdefault("ZSH_DB_PORT", "5432")

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()


class BackendInfrastructureTests(unittest.TestCase):
    def test_health_endpoint(self):
        response = Client().get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("timestamp", data)

    def test_readiness_endpoint_returns_non_sensitive_status(self):
        response = Client().get("/api/v1/ready/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ready")
        self.assertIn("checks", data)
        self.assertNotIn("password", data)

    def test_jalali_date_conversion_api(self):
        response = Client().get(
            "/api/v1/calendar/convert-date/",
            {"calendar": "jalali", "date": "۱۴۰۴/۰۱/۰۱"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "gregorian": "2025-03-21",
            "jalali": "1404/01/01",
        })

    def test_jalali_leap_day_conversion_api(self):
        response = Client().get(
            "/api/v1/calendar/convert-date/",
            {"calendar": "gregorian", "date": "2025-03-20"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "gregorian": "2025-03-20",
            "jalali": "1403/12/30",
        })

    def test_date_conversion_rejects_invalid_input(self):
        client = Client()
        for params in (
            {"calendar": "unknown", "date": "1404/01/01"},
            {"calendar": "jalali", "date": "1404/12/30"},
            {"calendar": "gregorian", "date": "2025-02-29"},
            {"calendar": "gregorian", "date": "2025-03-21T00:00:00"},
            {"calendar": "jalali"},
        ):
            with self.subTest(params=params):
                response = client.get("/api/v1/calendar/convert-date/", params)
                self.assertEqual(response.status_code, 400)
                self.assertIn("code", response.json())


if __name__ == "__main__":
    unittest.main()
