from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from ..models import GymExercise, GymWorkout


@transaction.atomic
def reorder_workout_exercises(*, workout_pk, user, ordered_ids):
    workout = get_object_or_404(
        GymWorkout.objects.select_for_update(),
        pk=workout_pk,
        user=user,
    )

    if not workout.is_in_progress:
        raise ValidationError(
            "Only an ongoing workout can be reordered."
        )

    existing = list(
        GymExercise.objects.select_for_update()
        .filter(workout=workout)
        .order_by("position", "pk")
    )

    try:
        requested = [int(value) for value in ordered_ids]
    except (TypeError, ValueError):
        raise ValidationError("The exercise order is invalid.") from None

    if (
        len(requested) != len(existing)
        or len(set(requested)) != len(requested)
        or set(requested) != {entry.pk for entry in existing}
    ):
        raise ValidationError(
            "The exercise list changed. Refresh before reordering again."
        )

    if requested == [entry.pk for entry in existing]:
        return

    highest = max(
        (entry.position for entry in existing),
        default=0,
    )

    if highest + len(existing) > 32767:
        raise ValidationError(
            "The exercise order is too large to rearrange safely."
        )

    for offset, entry in enumerate(existing, start=1):
        GymExercise.objects.filter(pk=entry.pk).update(
            position=highest + offset,
        )

    for position, entry_pk in enumerate(requested, start=1):
        GymExercise.objects.filter(pk=entry_pk).update(
            position=position,
        )