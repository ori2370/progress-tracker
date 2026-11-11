from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    ExerciseDefinition,
    ExerciseTrackingMode,
    GymExercise,
    GymSet,
    GymWorkout,
)


class TimedActivityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="timed_owner")

        self.workout = GymWorkout.objects.create(
            user=self.user,
            title="Mobility",
            date=timezone.localdate(),
        )
        self.activity = GymExercise.objects.create(
            workout=self.workout,
            name="Yoga",
            position=1,
            tracking_mode=ExerciseTrackingMode.DURATION,
        )

        self.client.force_login(self.user)

    def test_one_time_activity_can_use_duration(self):
        response = self.client.post(
            reverse(
                "tracking:gym-exercise-create",
                args=[self.workout.pk],
            ),
            {
                "new_name": "Stretching",
                "tracking_mode": "duration",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "tracking:gym-workout-detail",
                args=[self.workout.pk],
            ),
        )

        activity = self.workout.exercises.get(name="Stretching")
        self.assertEqual(
            activity.tracking_mode,
            ExerciseTrackingMode.DURATION,
        )
        self.assertIsNone(activity.definition)
        self.assertFalse(
            ExerciseDefinition.objects.filter(name="Stretching").exists()
        )

    def test_new_library_activity_preserves_selected_mode(self):
        self.client.post(
            reverse(
                "tracking:gym-exercise-create",
                args=[self.workout.pk],
            ),
            {
                "new_name": "Plank",
                "tracking_mode": "duration",
                "save_to_library": "on",
            },
        )

        definition = ExerciseDefinition.objects.get(
            user=self.user,
            name="Plank",
        )
        activity = self.workout.exercises.get(name="Plank")

        self.assertEqual(definition.tracking_mode, "duration")
        self.assertEqual(activity.tracking_mode, "duration")
        self.assertEqual(activity.definition, definition)

    def test_library_activity_uses_its_saved_mode(self):
        definition = ExerciseDefinition.objects.create(
            user=self.user,
            name="Cycling",
            tracking_mode="duration",
        )

        response = self.client.post(
            reverse(
                "tracking:gym-exercise-create",
                args=[self.workout.pk],
            ),
            {
                "definition": definition.pk,
                "tracking_mode": "strength",
            },
        )

        self.assertEqual(response.status_code, 302)
        activity = self.workout.exercises.get(definition=definition)
        self.assertEqual(activity.tracking_mode, "duration")

    def test_duration_is_saved_without_reps_or_weight(self):
        response = self.client.post(
            reverse(
                "tracking:gym-set-create",
                args=[self.activity.pk],
            ),
            {
                "minutes": 2,
                "seconds": 30,
            },
        )

        self.assertEqual(response.status_code, 302)

        entry = self.activity.sets.get()
        self.assertEqual(entry.duration_seconds, 150)
        self.assertIsNone(entry.reps)
        self.assertIsNone(entry.weight_kg)
        self.assertEqual(entry.duration_display, "2 min 30 sec")

    def test_invalid_durations_are_rejected(self):
        url = reverse(
            "tracking:gym-set-create",
            args=[self.activity.pk],
        )

        for data in [
            {"minutes": 0, "seconds": 0},
            {"minutes": -1, "seconds": 0},
            {"minutes": 0, "seconds": 60},
        ]:
            with self.subTest(data=data):
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)

        self.assertFalse(self.activity.sets.exists())

    def test_duration_can_be_edited(self):
        entry = GymSet.objects.create(
            exercise=self.activity,
            number=1,
            duration_seconds=60,
        )

        response = self.client.post(
            reverse("tracking:gym-set-update", args=[entry.pk]),
            {"minutes": 3, "seconds": 15},
        )

        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()

        self.assertEqual(entry.duration_seconds, 195)
        self.assertEqual(entry.number, 1)
        self.assertIsNone(entry.reps)
        self.assertIsNone(entry.weight_kg)

    def test_strength_activity_still_requires_reps_and_weight(self):
        strength = GymExercise.objects.create(
            workout=self.workout,
            name="Squat",
            position=2,
            tracking_mode="strength",
        )

        response = self.client.post(
            reverse(
                "tracking:gym-set-create",
                args=[strength.pk],
            ),
            {"minutes": 2, "seconds": 30},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("reps", response.context["form"].errors)
        self.assertIn("weight_kg", response.context["form"].errors)
        self.assertFalse(strength.sets.exists())

    def test_longest_duration_is_personal_best(self):
        definition = ExerciseDefinition.objects.create(
            user=self.user,
            name="Yoga",
            tracking_mode="duration",
        )
        self.activity.definition = definition
        self.activity.save()

        GymSet.objects.create(
            exercise=self.activity,
            number=1,
            duration_seconds=60,
        )
        best = GymSet.objects.create(
            exercise=self.activity,
            number=2,
            duration_seconds=150,
        )

        response = self.client.get(
            reverse(
                "tracking:gym-set-create",
                args=[self.activity.pk],
            )
        )

        self.assertEqual(response.context["personal_best"], best)
        self.assertContains(response, "2 min 30 sec")