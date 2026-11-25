from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    def test_liveness_does_not_query_database(self):
        with patch("config.health.connection.cursor") as cursor:
            response = self.client.get(reverse("health-live"))

        cursor.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "alive"})
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_readiness_with_available_database(self):
        response = self.client.get(reverse("health-ready"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    def test_readiness_with_unavailable_database(self):
        with patch(
            "config.health.connection.cursor",
            side_effect=OperationalError("Sensitive connection details"),
        ):
            response = self.client.get(reverse("health-ready"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "not_ready"})
        self.assertNotContains(
            response,
            "Sensitive connection details",
            status_code=503,
        )