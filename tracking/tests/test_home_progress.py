from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from tracking.models import (
    BodyMeasurement,
    GymWorkout,
    TennisSession,
)


@override_settings(TIME_ZONE="Asia/Jerusalem")
class HomeProgressTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="progress-owner",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-progress-owner",
        )
        self.client.force_login(self.user)

        self.today = date(2026, 11, 26)
        date_patch = patch(
            "django.utils.timezone.localdate",
            return_value=self.today,
        )
        date_patch.start()
        self.addCleanup(date_patch.stop)

    def create_gym(self, date_value, **kwargs):
        return GymWorkout.objects.create(
            user=kwargs.pop("user", self.user),
            date=date_value,
            title="Test workout",
            **kwargs,
        )

    def create_tennis(self, date_value, **kwargs):
        return TennisSession.objects.create(
            user=kwargs.pop("user", self.user),
            date=date_value,
            session_type="practice",
            focus="Test practice",
            **kwargs,
        )

    def test_counts_include_only_own_completed_sessions_this_month(self):
        self.create_gym(date(2026, 11, 1))
        self.create_gym(self.today)
        self.create_tennis(self.today)

        for create in (self.create_gym, self.create_tennis):
            create(date(2026, 10, 31))
            create(date(2026, 12, 1))
            create(date(2026, 11, 27))
            create(self.today, user=self.other_user)
            create(
                self.today,
                status="in_progress",
                started_at=datetime(
                    2026, 11, 26, 8,
                    tzinfo=dt_timezone.utc,
                ),
            )

        response = self.client.get(reverse("tracking:home"))

        self.assertEqual(response.context["gym_completed_count"], 2)
        self.assertEqual(response.context["tennis_completed_count"], 1)
        self.assertEqual(response.context["total_completed_count"], 3)
        self.assertContains(response, "November 2026")

    def test_month_rollover_handles_december_and_january(self):
        self.create_gym(date(2026, 12, 31))
        self.create_gym(date(2027, 1, 1))

        for today, expected_month in (
            (date(2026, 12, 31), "December 2026"),
            (date(2027, 1, 1), "January 2027"),
        ):
            with self.subTest(today=today):
                with patch(
                    "django.utils.timezone.localdate",
                    return_value=today,
                ):
                    response = self.client.get(
                        reverse("tracking:home")
                    )

                self.assertEqual(
                    response.context["gym_completed_count"],
                    1,
                )
                self.assertContains(response, expected_month)

    def test_weight_only_entry_preserves_latest_waist(self):
        waist_entry = BodyMeasurement.objects.create(
            user=self.user,
            date=self.today - timedelta(days=1),
            weight_kg=Decimal("74.00"),
            waist_cm=Decimal("88.00"),
        )
        weight_entry = BodyMeasurement.objects.create(
            user=self.user,
            date=self.today,
            weight_kg=Decimal("73.50"),
        )

        for page in ("home", "profile"):
            with self.subTest(page=page):
                response = self.client.get(
                    reverse(f"tracking:{page}")
                )

                self.assertEqual(
                    response.context["latest_weight"],
                    weight_entry,
                )
                self.assertEqual(
                    response.context["latest_waist"],
                    waist_entry,
                )
                self.assertContains(response, "73.50 kg")
                self.assertContains(response, "88.00 cm")

    def test_measurements_exclude_other_users_and_future_entries(self):
        own_entry = BodyMeasurement.objects.create(
            user=self.user,
            date=self.today - timedelta(days=1),
            weight_kg=Decimal("73.50"),
            waist_cm=Decimal("88.00"),
        )
        BodyMeasurement.objects.create(
            user=self.other_user,
            date=self.today,
            weight_kg=Decimal("99.00"),
            waist_cm=Decimal("110.00"),
        )
        BodyMeasurement.objects.create(
            user=self.user,
            date=self.today + timedelta(days=1),
            weight_kg=Decimal("75.00"),
            waist_cm=Decimal("90.00"),
        )

        for page in ("home", "profile"):
            with self.subTest(page=page):
                response = self.client.get(
                    reverse(f"tracking:{page}")
                )

                self.assertEqual(
                    response.context["latest_weight"],
                    own_entry,
                )
                self.assertEqual(
                    response.context["latest_waist"],
                    own_entry,
                )

    def test_empty_progress_and_measurements(self):
        response = self.client.get(reverse("tracking:home"))

        self.assertEqual(response.context["total_completed_count"], 0)
        self.assertIsNone(response.context["latest_weight"])
        self.assertIsNone(response.context["latest_waist"])
        self.assertContains(response, "Not recorded yet")

    def test_home_progress_links_open_overviews(self):
        response = self.client.get(reverse("tracking:home"))

        for name in (
            "gym-workout-list",
            "tennis-list",
            "measurement-list",
            "measurement-create",
        ):
            with self.subTest(link=name):
                self.assertContains(
                    response,
                    f'href="{reverse(f"tracking:{name}")}"',
                )