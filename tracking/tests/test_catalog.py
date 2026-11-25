import copy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from tracking.models import CatalogExercise, ExerciseDefinition


class CatalogImportTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "exercises.json"

        self.record = {
            "id": "Example_Squat",
            "name": "Example Squat",
            "equipment": "barbell",
            "category": "strength",
            "level": "beginner",
            "primaryMuscles": ["quadriceps"],
            "secondaryMuscles": ["glutes"],
            "instructions": ["Stand upright.", "", "Return slowly."],
        }

    def import_records(self, records):
        self.path.write_text(
            json.dumps(records),
            encoding="utf-8",
        )
        call_command(
            "import_exercise_catalog",
            str(self.path),
            stdout=io.StringIO(),
        )

    def test_import_removes_blank_instructions(self):
        self.import_records([self.record])

        exercise = CatalogExercise.objects.get(
            source_id="Example_Squat"
        )

        self.assertEqual(
            exercise.instructions,
            ["Stand upright.", "Return slowly."],
        )

    def test_repeated_import_updates_without_duplicates(self):
        self.import_records([self.record])
        original_pk = CatalogExercise.objects.get().pk

        updated = copy.deepcopy(self.record)
        updated["name"] = "Updated Squat"
        self.import_records([updated])

        self.assertEqual(CatalogExercise.objects.count(), 1)
        exercise = CatalogExercise.objects.get()
        self.assertEqual(exercise.pk, original_pk)
        self.assertEqual(exercise.name, "Updated Squat")

    def test_invalid_entry_prevents_partial_import(self):
        invalid = copy.deepcopy(self.record)
        invalid["id"] = "Invalid_Exercise"
        invalid["instructions"] = [123]

        with self.assertRaises(CommandError):
            self.import_records([self.record, invalid])

        self.assertFalse(CatalogExercise.objects.exists())

    def test_duplicate_source_ids_are_rejected(self):
        with self.assertRaises(CommandError):
            self.import_records([self.record, self.record])

        self.assertFalse(CatalogExercise.objects.exists())

    def test_refresh_preserves_personal_exercise_data(self):
        self.import_records([self.record])
        catalog = CatalogExercise.objects.get()
        user = get_user_model().objects.create_user(
            username="catalog-owner"
        )
        personal = ExerciseDefinition.objects.create(
            user=user,
            catalog_exercise=catalog,
            name="My squat",
            notes="Personal notes",
            video_url="https://www.youtube.com/watch?v=abcdefghijk",
        )

        updated = copy.deepcopy(self.record)
        updated["name"] = "Updated catalog squat"
        self.import_records([updated])

        personal.refresh_from_db()
        self.assertEqual(personal.name, "My squat")
        self.assertEqual(personal.notes, "Personal notes")
        self.assertEqual(
            personal.video_url,
            "https://www.youtube.com/watch?v=abcdefghijk",
        )


class CatalogViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="catalog-user")
        self.other_user = User.objects.create_user(
            username="catalog-other"
        )
        self.catalog = CatalogExercise.objects.create(
            source_id="Example_Squat",
            name="Example Squat",
            equipment="barbell",
            category="strength",
            level="beginner",
        )
        CatalogExercise.objects.create(
            source_id="Example_Curl",
            name="Example Curl",
            equipment="dumbbell",
            category="strength",
            level="beginner",
        )
        self.list_url = reverse("tracking:exercise-catalog")
        self.create_url = (
            reverse("tracking:exercise-create")
            + f"?catalog={self.catalog.pk}"
        )

    def test_catalog_requires_login(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)

    def test_search_and_equipment_filter(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            self.list_url,
            {"q": "squat", "equipment": "barbell"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Example Squat")
        self.assertNotContains(response, "Example Curl")

    def test_catalog_prefills_personal_exercise_form(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.create_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].initial["name"],
            "Example Squat",
        )
        self.assertEqual(
            response.context["form"].initial["equipment"],
            "barbell",
        )

    def test_creation_links_catalog_and_assigns_signed_in_user(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.create_url,
            {
                "name": "My squat",
                "equipment": "barbell",
                "tracking_mode": "strength",
                "user": self.other_user.pk,
            },
        )

        exercise = ExerciseDefinition.objects.get(name="My squat")
        self.assertEqual(exercise.user, self.owner)
        self.assertEqual(exercise.catalog_exercise, self.catalog)
        self.assertRedirects(
            response,
            reverse("tracking:exercise-list"),
        )

    def test_duplicate_personal_exercise_is_not_created(self):
        self.client.force_login(self.owner)
        data = {
            "name": "My squat",
            "equipment": "barbell",
            "tracking_mode": "strength",
        }

        self.client.post(self.create_url, data)
        response = self.client.post(self.create_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(
            ExerciseDefinition.objects.filter(
                user=self.owner,
                name="My squat",
            ).count(),
            1,
        )

    def test_unknown_catalog_entry_returns_404(self):
        self.client.force_login(self.owner)
        url = reverse("tracking:exercise-create") + "?catalog=999999"

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)