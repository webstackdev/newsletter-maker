from unittest.mock import patch

from django.test import TestCase


class HealthCheckTests(TestCase):
    def test_root_redirects_to_admin(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/admin/")

    def test_healthz_returns_ok(self):
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @patch("core.views._check_database", return_value=True)
    @patch("core.views._check_qdrant", return_value=True)
    def test_readyz_returns_ok_when_dependencies_are_ready(self, qdrant_check, database_check):
        response = self.client.get("/readyz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checks"], {"database": True, "qdrant": True})

    @patch("core.views._check_database", return_value=True)
    @patch("core.views._check_qdrant", return_value=False)
    def test_readyz_returns_service_unavailable_when_dependency_fails(self, qdrant_check, database_check):
        response = self.client.get("/readyz/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "degraded")
