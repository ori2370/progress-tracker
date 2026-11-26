from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tracking.models import (
    ExerciseDefinition,
    ExerciseTrackingMode,
    GymExercise,
    GymSet,
    GymWorkout,
)
from tracking.services.weight_suggestions import previous_weight_sets


class WeightSuggestionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="suggestion_owner")
        self.other = User.objects.create_user(username="suggestion_other")
        self.today = timezone.localdate()

        self.definition = ExerciseDefinition.objects.create(
            user=self.owner,
            name="Leg press",
        )
        self.current = self.make_exercise(
            self.today,
            active=True,
        )
        self.client.force_login(self.owner)

    def make_exercise(self, date, *, active=False, user=None):
        user = user or self.owner
        workout_data = {
            "user": user,
            "title": "Test workout",
            "date": date,
        }

        if active:
            workout_data.update({
                "status": GymWorkout.Status.IN_PROGRESS,
                "started_at": timezone.now(),
            })

        workout = GymWorkout.objects.create(**workout_data)

        definition = self.definition
        if user != self.owner:
            definition = ExerciseDefinition.objects.create(
                user=user,
                name="Leg press",
            )

        return GymExercise.objects.create(
            workout=workout,
            definition=definition,
            name="Leg press",
            position=1,
        )

    def add_set(self, exercise, number=1, weight="40.00", basis="total"):
        return GymSet.objects.create(
            exercise=exercise,
            number=number,
            reps=8,
            weight_kg=weight,
            weight_basis=basis,
        )

    def test_uses_latest_earlier_completed_workout(self):
        older = self.make_exercise(self.today - timedelta(days=4))
        self.add_set(older, weight="30.00")

        previous = self.make_exercise(self.today - timedelta(days=2))
        first = self.add_set(previous, weight="40.00", basis="per_side")
        second = self.add_set(
            previous,
            number=2,
            weight="45.00",
            basis="per_side",
        )

        active = self.make_exercise(
            self.today - timedelta(days=1),
            active=True,
        )
        self.add_set(active, weight="90.00")

        future = self.make_exercise(self.today + timedelta(days=1))
        self.add_set(future, weight="100.00")

        self.add_set(self.current, weight="50.00")

        self.assertEqual(
            previous_weight_sets(self.current),
            [first, second],
        )

    def test_unknown_basis_is_not_suggested(self):
        previous = self.make_exercise(self.today - timedelta(days=1))
        self.add_set(previous, basis="")

        self.assertEqual(previous_weight_sets(self.current), [])

    def test_other_users_history_is_not_suggested(self):
        previous = self.make_exercise(
            self.today - timedelta(days=1),
            user=self.other,
        )
        self.add_set(previous)

        self.assertEqual(previous_weight_sets(self.current), [])

    def test_suggestion_matches_set_number_without_prefilling(self):
        previous = self.make_exercise(self.today - timedelta(days=1))
        first = self.add_set(
            previous,
            weight="40.00",
            basis="per_side",
        )
        second = self.add_set(
            previous,
            number=2,
            weight="45.00",
            basis="per_side",
        )

        response = self.client.get(
            reverse("tracking:gym-sets-log", args=[self.current.pk])
        )
        rows = response.context["set_rows"]

        self.assertEqual(rows[0]["weight_suggestion"], first)
        self.assertEqual(rows[1]["weight_suggestion"], second)
        self.assertIsNone(rows[2]["weight_suggestion"])

        for row in rows:
            self.assertIsNone(row["form"]["weight_kg"].value())
            self.assertIsNone(row["form"]["reps"].value())

        self.assertContains(response, 'data-weight="40.00"')
        self.assertContains(response, 'data-basis="per_side"')
        self.assertEqual(self.current.sets.count(), 0)

    def test_timed_and_unlinked_exercises_have_no_weight_suggestion(self):
        previous = self.make_exercise(self.today - timedelta(days=1))
        self.add_set(previous)

        self.current.tracking_mode = ExerciseTrackingMode.DURATION
        self.current.save(update_fields=["tracking_mode"])
        self.assertEqual(previous_weight_sets(self.current), [])

        self.current.tracking_mode = ExerciseTrackingMode.STRENGTH
        self.current.definition = None
        self.current.save(
            update_fields=["tracking_mode", "definition"]
        )
        self.assertEqual(previous_weight_sets(self.current), [])

    def test_personal_bests_are_separated_by_basis(self):
        previous = self.make_exercise(self.today - timedelta(days=1))
        total = self.add_set(previous, weight="80.00", basis="total")
        side = self.add_set(
            previous,
            number=2,
            weight="45.00",
            basis="per_side",
        )
        unknown = self.add_set(
            previous,
            number=3,
            weight="100.00",
            basis="",
        )

        response = self.client.get(
            reverse("tracking:gym-sets-log", args=[self.current.pk])
        )

        self.assertIsNone(response.context["personal_best"])
        self.assertCountEqual(
            response.context["multiple_weight_bests"],
            [total, side, unknown],
        )

    def test_selected_basis_without_set_values_does_not_create_a_set(self):
        response = self.client.post(
            reverse("tracking:gym-sets-log", args=[self.current.pk]),
            {
                "action": "save",
                "sets-TOTAL_FORMS": "3",
                "sets-INITIAL_FORMS": "3",
                "sets-MIN_NUM_FORMS": "0",
                "sets-MAX_NUM_FORMS": "20",
                "sets-0-weight_basis": "per_side",
                "sets-1-weight_basis": "total",
                "sets-2-weight_basis": "total",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.current.sets.count(), 0)
        self.assertContains(
            response,
            "Fill at least one set before saving.",
        )