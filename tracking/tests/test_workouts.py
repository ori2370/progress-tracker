from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import (
    ExerciseDefinition,
    GymExercise,
    GymSet,
    GymWorkout,
    TemplateExercise,
    WorkoutRoutine,
    WorkoutTemplate,
)


class GymWorkoutTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="workout_owner")
        self.other = User.objects.create_user(username="workout_other")
        self.today = timezone.localdate()

        self.definition = ExerciseDefinition.objects.create(
            user=self.owner,
            name="Leg press",
            goal_weight_kg=Decimal("100.00"),
            goal_reps=10,
        )
        self.routine = WorkoutRoutine.objects.create(
            user=self.owner,
            name="Full body A/B",
            sessions_per_week=3,
        )
        self.template = WorkoutTemplate.objects.create(
            routine=self.routine,
            name="FBW A",
        )
        self.template_entry = TemplateExercise.objects.create(
            template=self.template,
            definition=self.definition,
            position=1,
            planned_sets=3,
            target_reps=10,
        )

        self.workout = GymWorkout.objects.create(
            user=self.owner,
            title="FBW B",
            date=self.today,
        )
        self.exercise = GymExercise.objects.create(
            workout=self.workout,
            definition=self.definition,
            name="Leg press",
            position=1,
        )

        self.client.force_login(self.owner)

    def test_starting_template_copies_exercises_without_creating_sets(self):
        response = self.client.post(
            reverse(
                "tracking:gym-workout-start",
                args=[self.template.pk],
            ),
            {
                "date": self.today.isoformat(),
                "title": "Today's FBW A",
            },
        )

        workout = GymWorkout.objects.get(title="Today's FBW A")
        self.assertRedirects(
            response,
            reverse("tracking:gym-workout-detail", args=[workout.pk]),
        )
        self.assertEqual(workout.user, self.owner)
        self.assertEqual(workout.source_template, self.template)

        exercise = workout.exercises.get()
        self.assertEqual(exercise.definition, self.definition)
        self.assertEqual(exercise.position, 1)
        self.assertEqual(exercise.sets.count(), 0)

        self.template_entry.refresh_from_db()
        self.assertEqual(self.template_entry.planned_sets, 3)

    def test_template_changes_do_not_change_logged_workout(self):
        self.client.post(
            reverse(
                "tracking:gym-workout-start",
                args=[self.template.pk],
            ),
            {
                "date": self.today.isoformat(),
                "title": "Saved workout",
            },
        )
        workout = GymWorkout.objects.get(title="Saved workout")
        exercise = workout.exercises.get()

        self.template_entry.delete()
        self.template.name = "Renamed template"
        self.template.save()

        workout.refresh_from_db()
        exercise.refresh_from_db()

        self.assertEqual(workout.title, "Saved workout")
        self.assertEqual(exercise.name, "Leg press")
        self.assertEqual(exercise.definition, self.definition)

    def test_empty_template_cannot_start_a_workout(self):
        self.template_entry.delete()
        before = GymWorkout.objects.count()

        response = self.client.post(
            reverse(
                "tracking:gym-workout-start",
                args=[self.template.pk],
            ),
            {
                "date": self.today.isoformat(),
                "title": "Empty workout",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Add at least one exercise to this template first.",
        )
        self.assertEqual(GymWorkout.objects.count(), before)

    def test_add_one_time_activity_without_saving_to_library(self):
        response = self.client.post(
            reverse(
                "tracking:gym-exercise-create",
                args=[self.workout.pk],
            ),
            {
                "new_name": "Yoga",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "tracking:gym-workout-detail",
                args=[self.workout.pk],
            ),
        )
        activity = self.workout.exercises.get(name="Yoga")
        self.assertIsNone(activity.definition)
        self.assertEqual(activity.position, 2)
        self.assertFalse(
            ExerciseDefinition.objects.filter(name="Yoga").exists()
        )

    def test_new_exercise_can_be_saved_to_library(self):
        self.client.post(
            reverse(
                "tracking:gym-exercise-create",
                args=[self.workout.pk],
            ),
            {
                "new_name": "Cable row",
                "save_to_library": "on",
            },
        )

        definition = ExerciseDefinition.objects.get(
            user=self.owner,
            name="Cable row",
        )
        exercise = self.workout.exercises.get(name="Cable row")
        self.assertEqual(exercise.definition, definition)

    def test_cannot_add_another_users_library_exercise(self):
        private_definition = ExerciseDefinition.objects.create(
            user=self.other,
            name="Private exercise",
        )
        before = self.workout.exercises.count()

        response = self.client.post(
            reverse(
                "tracking:gym-exercise-create",
                args=[self.workout.pk],
            ),
            {"definition": private_definition.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("definition", response.context["form"].errors)
        self.assertEqual(self.workout.exercises.count(), before)

    def test_sets_are_numbered_and_can_be_edited(self):
        url = reverse(
            "tracking:gym-set-create",
            args=[self.exercise.pk],
        )

        for reps, weight in [(10, "70.00"), (8, "75.00")]:
            response = self.client.post(
                url,
                {"reps": reps, "weight_kg": weight},
            )
            self.assertRedirects(response, url)

        sets = list(self.exercise.sets.all())
        self.assertEqual(
            [entry.number for entry in sets],
            [1, 2],
        )

        response = self.client.post(
            reverse(
                "tracking:gym-set-update",
                args=[sets[1].pk],
            ),
            {"reps": 9, "weight_kg": "75.00"},
        )

        self.assertRedirects(
            response,
            reverse(
                "tracking:gym-sets-log",
                args=[self.exercise.pk],
            ),
        )

        sets[1].refresh_from_db()
        self.assertEqual(sets[1].reps, 9)
        self.assertEqual(sets[1].number, 2)

    def test_shared_history_and_best_are_available_across_workouts(self):
        previous_workout = GymWorkout.objects.create(
            user=self.owner,
            title="Previous FBW A",
            date=self.today - timedelta(days=2),
        )
        previous_exercise = GymExercise.objects.create(
            workout=previous_workout,
            definition=self.definition,
            name="Leg press",
            position=1,
        )
        best = GymSet.objects.create(
            exercise=previous_exercise,
            number=1,
            reps=10,
            weight_kg=Decimal("80.00"),
        )

        response = self.client.get(
            reverse(
                "tracking:gym-set-create",
                args=[self.exercise.pk],
            )
        )

        self.assertEqual(
            response.context["previous_performance"],
            previous_exercise,
        )
        self.assertEqual(response.context["personal_best"], best)
        self.assertEqual(
            response.context["exercise_definition"].goal_reps,
            10,
        )
        self.assertContains(
            response,
            reverse(
                "tracking:gym-workout-detail",
                args=[previous_workout.pk],
            ),
        )

    def test_personal_best_uses_reps_to_break_weight_ties(self):
        GymSet.objects.create(
            exercise=self.exercise,
            number=1,
            reps=8,
            weight_kg=Decimal("80.00"),
        )
        best = GymSet.objects.create(
            exercise=self.exercise,
            number=2,
            reps=10,
            weight_kg=Decimal("80.00"),
        )

        response = self.client.get(
            reverse(
                "tracking:gym-set-create",
                args=[self.exercise.pk],
            )
        )

        self.assertEqual(response.context["personal_best"], best)
        self.assertIsNone(response.context["previous_performance"])

    def test_delete_requires_post_and_preserves_library_and_template(self):
        recorded_set = GymSet.objects.create(
            exercise=self.exercise,
            number=1,
            reps=10,
            weight_kg=Decimal("70.00"),
        )
        url = reverse(
            "tracking:gym-workout-delete",
            args=[self.workout.pk],
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            GymWorkout.objects.filter(pk=self.workout.pk).exists()
        )

        response = self.client.post(url)
        self.assertRedirects(
            response,
            reverse("tracking:gym-workout-list"),
        )

        self.assertFalse(
            GymWorkout.objects.filter(pk=self.workout.pk).exists()
        )
        self.assertFalse(
            GymExercise.objects.filter(pk=self.exercise.pk).exists()
        )
        self.assertFalse(
            GymSet.objects.filter(pk=recorded_set.pk).exists()
        )
        self.assertTrue(
            ExerciseDefinition.objects.filter(
                pk=self.definition.pk
            ).exists()
        )
        self.assertTrue(
            WorkoutTemplate.objects.filter(pk=self.template.pk).exists()
        )

    def test_other_user_cannot_access_or_modify_workout_data(self):
        recorded_set = GymSet.objects.create(
            exercise=self.exercise,
            number=1,
            reps=10,
            weight_kg=Decimal("70.00"),
        )
        self.client.force_login(self.other)

        urls = [
            reverse(
                "tracking:gym-workout-detail",
                args=[self.workout.pk],
            ),
            reverse(
                "tracking:gym-workout-delete",
                args=[self.workout.pk],
            ),
            reverse(
                "tracking:gym-exercise-create",
                args=[self.workout.pk],
            ),
            reverse(
                "tracking:gym-set-create",
                args=[self.exercise.pk],
            ),
            reverse(
                "tracking:gym-set-update",
                args=[recorded_set.pk],
            ),
            reverse(
                "tracking:gym-workout-start",
                args=[self.template.pk],
            ),
        ]

        detail_url = reverse(
            "tracking:gym-workout-detail",
            args=[self.workout.pk],
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

                expected_status = 405 if url == detail_url else 404

                self.assertEqual(
                    self.client.post(
                        url,
                        {
                            "date": self.today.isoformat(),
                            "title": "Unauthorized",
                            "new_name": "Unauthorized",
                            "reps": 1,
                            "weight_kg": "1.00",
                        },
                    ).status_code,
                    expected_status,
                )

        recorded_set.refresh_from_db()
        self.assertEqual(recorded_set.reps, 10)
        self.assertTrue(
            GymWorkout.objects.filter(pk=self.workout.pk).exists()
        )