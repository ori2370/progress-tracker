from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tracking.models import (
    ExerciseTrackingMode,
    GymExercise,
    GymSet,
    GymWorkout,
)


class WorkoutSetsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="sets_owner")
        self.other = User.objects.create_user(username="sets_other")

        self.workout = GymWorkout.objects.create(
            user=self.owner,
            title="Test workout",
            date=timezone.localdate(),
        )
        self.exercise = GymExercise.objects.create(
            workout=self.workout,
            name="Leg press",
            position=1,
            planned_sets=3,
        )
        self.url = reverse(
            "tracking:gym-sets-log",
            args=[self.exercise.pk],
        )
        self.client.force_login(self.owner)

    def payload(self, rows, **extra):
        data = {
            "action": "save",
            "sets-TOTAL_FORMS": str(len(rows)),
            "sets-INITIAL_FORMS": str(len(rows)),
            "sets-MIN_NUM_FORMS": "0",
            "sets-MAX_NUM_FORMS": "20",
        }

        for index, row in enumerate(rows):
            for name, value in row.items():
                data[f"sets-{index}-{name}"] = value

        data.update(extra)
        return data

    def record_strength_sets(self, count):
        for number in range(1, count + 1):
            GymSet.objects.create(
                exercise=self.exercise,
                number=number,
                reps=8,
                weight_kg="50.00",
            )

    def test_only_filled_rows_are_saved(self):
        response = self.client.post(
            self.url,
            self.payload([
                {"reps": "8", "weight_kg": "50.00"},
                {"reps": "7", "weight_kg": "50.00"},
                {},
            ]),
        )

        self.assertRedirects(response, self.url)
        self.assertEqual(
            list(self.exercise.sets.values_list("number", flat=True)),
            [1, 2],
        )

        response = self.client.get(self.url)
        self.assertEqual(len(response.context["set_rows"]), 1)
        self.assertEqual(response.context["set_rows"][0]["number"], 3)

    def test_goal_completion_requires_requesting_an_extra_row(self):
        self.record_strength_sets(3)

        response = self.client.get(self.url)
        self.assertTrue(response.context["goal_reached"])
        self.assertEqual(response.context["set_rows"], [])
        self.assertContains(response, "All 3 planned sets recorded")
        self.assertContains(response, "Add another set")

        response = self.client.get(self.url, {"extra": "1"})
        self.assertEqual(len(response.context["set_rows"]), 1)
        self.assertEqual(response.context["set_rows"][0]["number"], 4)
        self.assertContains(response, "Fill from previous set")

        response = self.client.post(
            self.url,
            self.payload(
                [{"reps": "6", "weight_kg": "55.00"}],
                extra="1",
            ),
        )

        self.assertRedirects(response, self.url)
        self.assertEqual(self.exercise.sets.count(), 4)
        self.assertEqual(
            self.client.get(self.url).context["set_rows"],
            [],
        )

    def test_invalid_row_prevents_partial_saving(self):
        response = self.client.post(
            self.url,
            self.payload([
                {"reps": "8", "weight_kg": "50.00"},
                {"reps": "7"},
                {},
            ]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "weight_kg",
            response.context["formset"].forms[1].errors,
        )
        self.assertEqual(self.exercise.sets.count(), 0)

    def test_empty_submission_does_not_create_sets(self):
        response = self.client.post(
            self.url,
            self.payload([{}, {}, {}]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Fill at least one set before saving.",
        )
        self.assertEqual(self.exercise.sets.count(), 0)

    def test_duration_rows_and_previous_set_data(self):
        self.exercise.tracking_mode = ExerciseTrackingMode.DURATION
        self.exercise.save(update_fields=["tracking_mode"])

        response = self.client.post(
            self.url,
            self.payload([
                {"minutes": "1", "seconds": "30"},
                {"minutes": "0", "seconds": "45"},
                {},
            ]),
        )

        self.assertRedirects(response, self.url)
        self.assertEqual(
            list(
                self.exercise.sets.values_list(
                    "duration_seconds",
                    flat=True,
                )
            ),
            [90, 45],
        )
        self.assertFalse(
            self.exercise.sets.filter(reps__isnull=False).exists()
        )

        response = self.client.get(self.url)
        self.assertContains(response, 'data-duration="45"')
        self.assertContains(response, "Fill from previous set")
        self.assertEqual(len(response.context["set_rows"]), 1)

    def test_plan_is_saved_for_this_exercise(self):
        response = self.client.post(
            self.url,
            {"action": "plan", "planned_sets": "2"},
        )

        self.assertRedirects(response, self.url)
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.planned_sets, 2)
        self.assertEqual(self.exercise.sets.count(), 0)
        self.assertEqual(
            len(self.client.get(self.url).context["set_rows"]),
            2,
        )

    def test_other_user_cannot_view_log_or_change_plan(self):
        self.client.force_login(self.other)

        self.assertEqual(
            self.client.get(self.url).status_code,
            404,
        )

        for data in [
            self.payload([
                {"reps": "8", "weight_kg": "50.00"},
                {},
                {},
            ]),
            {"action": "plan", "planned_sets": "1"},
        ]:
            with self.subTest(data=data):
                self.assertEqual(
                    self.client.post(self.url, data).status_code,
                    404,
                )

        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.planned_sets, 3)
        self.assertEqual(self.exercise.sets.count(), 0)