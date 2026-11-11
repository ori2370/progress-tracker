from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .gym_forms import BodyMeasurementForm
from .models import BodyMeasurement


class BodyMeasurementTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="gym_owner")
        self.other = User.objects.create_user(username="gym_other")
        self.today = timezone.localdate()
        self.url = reverse("tracking:measurement-list")

    def record(self, days_ago=0, user=None, weight=None, waist=None):
        return BodyMeasurement.objects.create(
            user=user or self.owner,
            date=self.today - timedelta(days=days_ago),
            weight_kg=weight,
            waist_cm=waist,
        )

    def test_pages_require_login(self):
        measurement = self.record(weight="71.00")

        urls = [
            self.url,
            reverse("tracking:measurement-create"),
            reverse(
                "tracking:measurement-update",
                args=[measurement.pk],
            ),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith("/admin/login/"))

    def test_weight_or_waist_can_be_recorded_independently(self):
        for values in [
            {"weight_kg": "71.00"},
            {"waist_cm": "85.00"},
            {"weight_kg": "71.00", "waist_cm": "85.00"},
        ]:
            with self.subTest(values=values):
                form = BodyMeasurementForm(
                    data={"date": self.today.isoformat(), **values}
                )
                self.assertTrue(form.is_valid(), form.errors)

    def test_empty_measurement_is_rejected(self):
        form = BodyMeasurementForm(
            data={"date": self.today.isoformat()}
        )

        self.assertFalse(form.is_valid())

    def test_measurements_must_be_positive(self):
        for field in ("weight_kg", "waist_cm"):
            for value in ("0", "-1"):
                with self.subTest(field=field, value=value):
                    form = BodyMeasurementForm(
                        data={
                            "date": self.today.isoformat(),
                            field: value,
                        }
                    )
                    self.assertFalse(form.is_valid())
                    self.assertIn(field, form.errors)

    def test_creation_assigns_signed_in_user(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("tracking:measurement-create"),
            {
                "date": self.today.isoformat(),
                "weight_kg": "71.25",
                "user": self.other.pk,
            },
        )

        self.assertRedirects(response, self.url)
        measurement = BodyMeasurement.objects.get()
        self.assertEqual(measurement.user, self.owner)
        self.assertIsNone(measurement.waist_cm)

    def test_other_users_records_are_hidden_and_cannot_be_edited(self):
        private_record = self.record(
            user=self.other,
            weight="99.99",
        )
        self.client.force_login(self.owner)

        response = self.client.get(self.url)
        self.assertEqual(list(response.context["measurements"]), [])

        edit_url = reverse(
            "tracking:measurement-update",
            args=[private_record.pk],
        )
        self.assertEqual(self.client.get(edit_url).status_code, 404)
        self.assertEqual(
            self.client.post(
                edit_url,
                {
                    "date": self.today.isoformat(),
                    "weight_kg": "50.00",
                },
            ).status_code,
            404,
        )

        private_record.refresh_from_db()
        self.assertEqual(private_record.weight_kg, Decimal("99.99"))

    def test_weekly_averages_use_correct_dates_and_owner(self):
        self.record(days_ago=0, weight="70.00")
        self.record(days_ago=6, weight="72.00")
        self.record(days_ago=7, weight="73.00")
        self.record(days_ago=13, weight="75.00")

        # These must not contribute to either weekly average.
        self.record(days_ago=14, weight="90.00")
        self.record(days_ago=-1, weight="90.00")
        self.record(user=self.other, weight="90.00")
        self.record(waist="85.00")

        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        context = response.context

        self.assertEqual(context["current_count"], 2)
        self.assertEqual(context["previous_count"], 2)
        self.assertEqual(context["current_average"], Decimal("71.00"))
        self.assertEqual(context["previous_average"], Decimal("74.00"))
        self.assertEqual(context["weight_change_display"], "-3.00")
        self.assertEqual(context["weight_direction"], "Decrease")

    def test_weekly_comparison_requires_both_periods(self):
        self.record(weight="71.00")
        self.client.force_login(self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.context["current_count"], 1)
        self.assertEqual(response.context["previous_count"], 0)
        self.assertFalse(
            response.context.get("weight_comparison_available", False)
        )

    def test_waist_trend_uses_latest_two_eligible_measurements(self):
        previous = self.record(days_ago=10, waist="86.00")
        latest = self.record(days_ago=1, waist="85.50")
        self.record(days_ago=20, waist="87.00")
        self.record(days_ago=0, weight="71.00")
        self.record(days_ago=-1, waist="80.00")
        self.record(user=self.other, waist="99.00")

        self.client.force_login(self.owner)
        response = self.client.get(self.url)

        self.assertEqual(response.context["latest_waist"], latest)
        self.assertEqual(response.context["previous_waist"], previous)
        self.assertEqual(
            response.context["waist_change_display"],
            "-0.50",
        )
        self.assertEqual(response.context["waist_direction"], "Decrease")