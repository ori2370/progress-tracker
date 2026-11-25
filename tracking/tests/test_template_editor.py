from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tracking.models import (
    ExerciseDefinition,
    ExerciseTrackingMode,
    TemplateExercise,
    WorkoutRoutine,
    WorkoutTemplate,
)


class TemplateEditorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="template-owner",
        )
        self.client.force_login(self.user)

        self.routine = WorkoutRoutine.objects.create(
            user=self.user,
            name="FBW A/B",
        )
        self.template = WorkoutTemplate.objects.create(
            routine=self.routine,
            name="FBW A",
        )

        self.entries = []

        for position, name in enumerate(
            ["Leg Press", "Leg Curl", "Pulldown"],
            start=1,
        ):
            definition = ExerciseDefinition.objects.create(
                user=self.user,
                name=name,
            )
            self.entries.append(
                TemplateExercise.objects.create(
                    template=self.template,
                    definition=definition,
                    position=position,
                    planned_sets=2,
                    target_reps=8,
                )
            )

        self.editor_url = reverse(
            "tracking:template-update",
            args=[self.template.pk],
        )
        self.overview_url = reverse(
            "tracking:routine-detail",
            args=[self.routine.pk],
        )
        self.add_url = reverse(
            "tracking:template-exercise-create",
            args=[self.template.pk],
        )

    def saved_order(self):
        return list(
            self.template.exercises.order_by("position").values_list(
                "pk", "position"
            )
        )

    def test_save_updates_details_and_order_then_returns_to_overview(self):
        first, second, third = self.entries

        response = self.client.post(
            self.editor_url,
            {
                "name": "Updated FBW A",
                "notes": "Updated notes",
                "exercise_order": [
                    third.pk,
                    first.pk,
                    second.pk,
                ],
            },
        )

        self.assertRedirects(response, self.overview_url)
        self.template.refresh_from_db()
        self.assertEqual(self.template.name, "Updated FBW A")
        self.assertEqual(self.template.notes, "Updated notes")
        self.assertEqual(
            self.saved_order(),
            [(third.pk, 1), (first.pk, 2), (second.pk, 3)],
        )

    def test_invalid_order_does_not_save_details_or_positions(self):
        original_order = self.saved_order()

        for invalid_order in (
            [self.entries[0].pk] * 3,
            [self.entries[0].pk],
            ["invalid"],
        ):
            with self.subTest(order=invalid_order):
                response = self.client.post(
                    self.editor_url,
                    {
                        "name": "Should not save",
                        "notes": "",
                        "exercise_order": invalid_order,
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertTrue(
                    response.context["form"].non_field_errors()
                )
                self.template.refresh_from_db()
                self.assertEqual(self.template.name, "FBW A")
                self.assertEqual(self.saved_order(), original_order)

    def test_other_user_cannot_save_template(self):
        other_user = get_user_model().objects.create_user(
            username="other-owner",
        )
        self.client.force_login(other_user)

        response = self.client.post(
            self.editor_url,
            {
                "name": "Unauthorized change",
                "notes": "",
                "exercise_order": [
                    entry.pk for entry in self.entries
                ],
            },
        )

        self.assertEqual(response.status_code, 404)
        self.template.refresh_from_db()
        self.assertEqual(self.template.name, "FBW A")

    def test_editing_position_shifts_other_exercises(self):
        first, second, third = self.entries
        url = reverse(
            "tracking:template-exercise-update",
            args=[third.pk],
        )

        response = self.client.post(
            url,
            {
                "definition": third.definition_id,
                "position": 1,
                "planned_sets": 3,
                "target_reps": 10,
            },
        )

        self.assertRedirects(response, self.editor_url)
        self.assertEqual(
            self.saved_order(),
            [(third.pk, 1), (first.pk, 2), (second.pk, 3)],
        )
        third.refresh_from_db()
        self.assertEqual(third.planned_sets, 3)
        self.assertEqual(third.target_reps, 10)

    def test_duration_target_is_saved_and_shown_in_overview(self):
        definition = ExerciseDefinition.objects.create(
            user=self.user,
            name="Stretch",
            tracking_mode=ExerciseTrackingMode.DURATION,
        )

        response = self.client.post(
            self.add_url,
            {
                "definition": definition.pk,
                "position": 4,
                "planned_sets": 1,
                "target_minutes": 2,
                "target_seconds": 30,
            },
        )

        self.assertRedirects(response, self.editor_url)

        entry = self.template.exercises.get(
            definition=definition,
        )
        self.assertEqual(entry.target_duration_seconds, 150)
        self.assertIsNone(entry.target_reps)

        response = self.client.get(self.overview_url)
        self.assertContains(response, entry.target_duration_display)

    def test_used_exercise_is_unavailable_and_duplicate_post_is_rejected(self):
        response = self.client.get(self.add_url)
        choices = response.context["form"].fields["definition"].queryset

        self.assertFalse(
            choices.filter(pk=self.entries[0].definition_id).exists()
        )

        response = self.client.post(
            self.add_url,
            {
                "definition": self.entries[0].definition_id,
                "position": 4,
                "planned_sets": 2,
                "target_reps": 8,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("definition", response.context["form"].errors)
        self.assertEqual(self.template.exercises.count(), 3)