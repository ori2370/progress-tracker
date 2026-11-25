import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tracking.models import CatalogExercise


class Command(BaseCommand):
    help = "Import exercise descriptions from a Free Exercise DB JSON file."

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)

    def handle(self, *args, **options):
        path = options["file"]

        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CommandError(f"Cannot read catalog: {error}") from error

        if not isinstance(records, list) or not records:
            raise CommandError("The catalog must be a non-empty JSON list.")

        exercises = []
        seen_ids = set()

        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                raise CommandError(f"Entry {index} must be an object.")

            values = {}

            for source, target in (
                ("id", "source_id"),
                ("name", "name"),
                ("category", "category"),
                ("level", "level"),
            ):
                value = record.get(source)

                if not isinstance(value, str) or not value.strip():
                    raise CommandError(
                        f"Entry {index}: {source} must be non-empty text."
                    )

                values[target] = value.strip()

            equipment = record.get("equipment")

            if equipment is not None and not isinstance(equipment, str):
                raise CommandError(
                    f"Entry {index}: equipment must be text or null."
                )

            values["equipment"] = (equipment or "").strip()

            for source, target in (
                ("primaryMuscles", "primary_muscles"),
                ("secondaryMuscles", "secondary_muscles"),
                ("instructions", "instructions"),
            ):
                value = record.get(source)

                if not isinstance(value, list) or any(
                    not isinstance(item, str)
                    for item in value
                ):
                    raise CommandError(
                        f"Entry {index}: {source} must be a list of text."
                    )

                values[target] = [
                    item.strip()
                    for item in value
                    if item.strip()
                ]
            source_id = values["source_id"]

            if source_id in seen_ids:
                raise CommandError(f"Duplicate catalog ID: {source_id}")

            seen_ids.add(source_id)

            exercise = CatalogExercise(**values)

            try:
                exercise.full_clean(validate_unique=False)
            except ValidationError as error:
                raise CommandError(
                    f"Invalid catalog entry {source_id}: {error}"
                ) from error

            exercises.append(values)

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for values in exercises:
                defaults = values.copy()
                source_id = defaults.pop("source_id")

                _, created = CatalogExercise.objects.update_or_create(
                    source_id=source_id,
                    defaults=defaults,
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported catalog: {created_count} created, "
                f"{updated_count} existing entries refreshed."
            )
        )