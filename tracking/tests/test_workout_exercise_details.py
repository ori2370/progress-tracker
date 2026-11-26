from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tracking.models import GymExercise, GymSet, GymWorkout


class WorkoutExerciseDetailsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="details_owner")
        self.other = User.objects.create_user(username="details_other")

        self.workout = GymWorkout.objects.create(
            user=self.owner,
            title="Completed workout",
            date=timezone.localdate(),
        )
        self.exercise = GymExercise.objects.create(
            workout=self.workout,
            name="Leg press",
            position=1,
        )
        self.sets = [
            GymSet.objects.create(
                exercise=self.exercise,
                number=number,
                reps=8,
                weight_kg=weight,
            )
            for number, weight in [
                (1, Decimal("40.00")),
                (2, Decimal("45.00")),
            ]
        ]

        self.editor_url = reverse(
            "tracking:gym-sets-log",
            args=[self.exercise.pk],
        )
        self.note_url = reverse(
            "tracking:gym-exercise-note",
            args=[self.exercise.pk],
        )
        self.basis_url = reverse(
            "tracking:gym-exercise-weight-basis",
            args=[self.exercise.pk],
        )
        self.edit_url = reverse(
            "tracking:gym-set-update",
            args=[self.sets[0].pk],
        )
        self.client.force_login(self.owner)

    def test_note_can_be_saved_and_cleared(self):
        for note in ["Seat position 4. Warm up first.", ""]:
            response = self.client.post(
                self.note_url,
                {"notes": note},
            )

            self.assertRedirects(response, self.editor_url)
            self.exercise.refresh_from_db()
            self.assertEqual(self.exercise.notes, note)
            self.assertEqual(self.exercise.sets.count(), 2)

    def test_invalid_note_preserves_saved_note(self):
        self.exercise.notes = "Keep this note"
        self.exercise.save(update_fields=["notes"])

        response = self.client.post(
            self.note_url,
            {"notes": "x" * 2001},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("notes", response.context["form"].errors)
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.notes, "Keep this note")

    def test_bulk_basis_changes_labels_only_and_then_disappears(self):
        response = self.client.get(self.editor_url)
        self.assertTrue(
            response.context["can_set_legacy_weight_basis"]
        )

        response = self.client.post(
            self.basis_url,
            {"weight_basis": "per_side"},
        )
        self.assertRedirects(response, self.editor_url)

        self.assertEqual(
            list(
                self.exercise.sets.values_list(
                    "reps", "weight_kg", "weight_basis"
                )
            ),
            [
                (8, Decimal("40.00"), "per_side"),
                (8, Decimal("45.00"), "per_side"),
            ],
        )

        for url in [self.editor_url, self.edit_url]:
            response = self.client.get(url)
            self.assertFalse(
                response.context["can_set_legacy_weight_basis"]
            )

    def test_bulk_action_from_set_editor_does_not_save_other_edits(self):
        response = self.client.get(self.edit_url)
        self.assertTrue(
            response.context["can_set_legacy_weight_basis"]
        )

        response = self.client.post(
            self.edit_url,
            {
                "action": "apply_basis",
                "weight_basis": "dumbbell",
                "reps": "99",
                "weight_kg": "999.00",
            },
        )
        self.assertRedirects(response, self.editor_url)

        self.sets[0].refresh_from_db()
        self.sets[1].refresh_from_db()

        self.assertEqual(self.sets[0].reps, 8)
        self.assertEqual(self.sets[0].weight_kg, Decimal("40.00"))
        self.assertEqual(self.sets[0].weight_basis, "dumbbell")
        self.assertEqual(self.sets[1].weight_basis, "dumbbell")

    def test_one_existing_basis_blocks_bulk_update(self):
        self.sets[0].weight_basis = "total"
        self.sets[0].save(update_fields=["weight_basis"])

        for url in [self.editor_url, self.edit_url]:
            response = self.client.get(url)
            self.assertFalse(
                response.context["can_set_legacy_weight_basis"]
            )

        response = self.client.post(
            self.basis_url,
            {"weight_basis": "per_side"},
        )
        self.assertEqual(response.status_code, 400)

        self.sets[0].refresh_from_db()
        self.sets[1].refresh_from_db()
        self.assertEqual(self.sets[0].weight_basis, "total")
        self.assertEqual(self.sets[1].weight_basis, "")

    def test_active_workout_blocks_legacy_bulk_update(self):
        self.workout.status = GymWorkout.Status.IN_PROGRESS
        self.workout.started_at = timezone.now()
        self.workout.save(
            update_fields=["status", "started_at"]
        )

        response = self.client.post(
            self.basis_url,
            {"weight_basis": "per_side"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            self.client.get(self.editor_url)
            .context["can_set_legacy_weight_basis"]
        )

    def test_other_user_cannot_change_notes_or_basis(self):
        self.client.force_login(self.other)

        for url, data in [
            (self.note_url, {"notes": "Unauthorized"}),
            (self.basis_url, {"weight_basis": "per_side"}),
            (
                self.edit_url,
                {
                    "action": "apply_basis",
                    "weight_basis": "per_side",
                },
            ),
        ]:
            with self.subTest(url=url):
                self.assertEqual(
                    self.client.post(url, data).status_code,
                    404,
                )

        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.notes, "")
        self.assertTrue(
            all(
                entry.weight_basis == ""
                for entry in self.exercise.sets.all()
            )
        )