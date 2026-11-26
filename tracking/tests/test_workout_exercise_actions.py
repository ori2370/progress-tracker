from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tracking.models import GymExercise, GymSet, GymWorkout


class WorkoutExerciseActionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="action_owner")
        self.other = User.objects.create_user(username="action_other")

        self.workout = GymWorkout.objects.create(
            user=self.owner,
            title="Active workout",
            date=timezone.localdate(),
            status=GymWorkout.Status.IN_PROGRESS,
            started_at=timezone.now(),
        )

        self.first = GymExercise.objects.create(
            workout=self.workout,
            name="First exercise",
            position=1,
            copied_from_template=True,
        )
        self.second = GymExercise.objects.create(
            workout=self.workout,
            name="Second exercise",
            position=2,
            copied_from_template=True,
        )
        self.manual = GymExercise.objects.create(
            workout=self.workout,
            name="Manual exercise",
            position=3,
        )

        self.order_url = reverse(
            "tracking:gym-workout-order",
            args=[self.workout.pk],
        )
        self.detail_url = reverse(
            "tracking:gym-workout-detail",
            args=[self.workout.pk],
        )
        self.client.force_login(self.owner)

    def inclusion_url(self, exercise):
        return reverse(
            "tracking:gym-exercise-inclusion",
            args=[exercise.pk],
        )

    def positions(self):
        return list(
            self.workout.exercises.values_list("pk", "position")
        )

    def finish_workout(self):
        self.workout.status = GymWorkout.Status.COMPLETED
        self.workout.finished_at = timezone.now()
        self.workout.save(
            update_fields=["status", "finished_at"]
        )

    def test_unstarted_template_exercise_can_be_omitted_and_restored(self):
        url = self.inclusion_url(self.first)

        for inclusion in ["omitted", "included"]:
            response = self.client.post(
                url,
                {"inclusion": inclusion},
            )
            self.assertRedirects(response, self.detail_url)
            self.first.refresh_from_db()
            self.assertEqual(self.first.inclusion, inclusion)

    def test_skipped_is_visible_but_omitted_is_hidden_after_finishing(self):
        self.client.post(
            self.inclusion_url(self.first),
            {"inclusion": "omitted"},
        )
        self.client.post(
            self.inclusion_url(self.second),
            {"inclusion": "skipped"},
        )
        self.finish_workout()

        response = self.client.get(self.detail_url)

        self.assertNotContains(response, "First exercise")
        self.assertContains(response, "Second exercise")
        self.assertContains(response, "Skipped")

    def test_recorded_exercise_cannot_be_skipped_or_omitted(self):
        recorded = GymSet.objects.create(
            exercise=self.first,
            number=1,
            reps=8,
            weight_kg="50.00",
        )

        for inclusion in ["skipped", "omitted"]:
            with self.subTest(inclusion=inclusion):
                response = self.client.post(
                    self.inclusion_url(self.first),
                    {"inclusion": inclusion},
                )
                self.assertEqual(response.status_code, 400)

        self.first.refresh_from_db()
        self.assertEqual(self.first.inclusion, "included")
        self.assertTrue(
            GymSet.objects.filter(pk=recorded.pk).exists()
        )

    def test_manual_exercise_cannot_be_skipped_or_omitted(self):
        for inclusion in ["skipped", "omitted"]:
            with self.subTest(inclusion=inclusion):
                response = self.client.post(
                    self.inclusion_url(self.manual),
                    {"inclusion": inclusion},
                )
                self.assertEqual(response.status_code, 400)

        self.manual.refresh_from_db()
        self.assertEqual(self.manual.inclusion, "included")

    def test_reordering_preserves_recorded_sets(self):
        recorded = GymSet.objects.create(
            exercise=self.first,
            number=1,
            reps=8,
            weight_kg="50.00",
        )

        response = self.client.post(
            self.order_url,
            {
                "exercise_order": [
                    self.manual.pk,
                    self.second.pk,
                    self.first.pk,
                ]
            },
        )

        self.assertRedirects(response, self.detail_url)
        self.assertEqual(
            self.positions(),
            [
                (self.manual.pk, 1),
                (self.second.pk, 2),
                (self.first.pk, 3),
            ],
        )

        recorded.refresh_from_db()
        self.assertEqual(recorded.exercise_id, self.first.pk)
        self.assertEqual(recorded.reps, 8)

    def test_invalid_orders_leave_positions_unchanged(self):
        original = self.positions()

        invalid_orders = [
            [self.first.pk, self.first.pk, self.manual.pk],
            [self.first.pk, self.second.pk],
            [self.first.pk, self.second.pk, 999999],
            ["invalid", self.second.pk, self.manual.pk],
        ]

        for order in invalid_orders:
            with self.subTest(order=order):
                response = self.client.post(
                    self.order_url,
                    {"exercise_order": order},
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.positions(), original)

    def test_finished_workout_rejects_selection_and_order_changes(self):
        self.finish_workout()
        original = self.positions()

        response = self.client.post(
            self.inclusion_url(self.first),
            {"inclusion": "skipped"},
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            self.order_url,
            {
                "exercise_order": [
                    self.manual.pk,
                    self.second.pk,
                    self.first.pk,
                ]
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.positions(), original)

        self.first.refresh_from_db()
        self.assertEqual(self.first.inclusion, "included")

    def test_other_user_cannot_change_selection_or_order(self):
        self.client.force_login(self.other)
        original = self.positions()

        response = self.client.post(
            self.inclusion_url(self.first),
            {"inclusion": "skipped"},
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            self.order_url,
            {
                "exercise_order": [
                    self.manual.pk,
                    self.second.pk,
                    self.first.pk,
                ]
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.positions(), original)

        self.first.refresh_from_db()
        self.assertEqual(self.first.inclusion, "included")