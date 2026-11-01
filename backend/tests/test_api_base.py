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


if __name__ == "__main__":
    unittest.main()
