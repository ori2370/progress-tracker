from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import TemplateExercise, WorkoutTemplate


@transaction.atomic
def save_template_exercise(*, entry, user):
    template = (
        WorkoutTemplate.objects
        .select_for_update()
        .filter(
            pk=entry.template_id,
            routine__user=user,
        )
        .first()
    )

    if template is None:
        raise ValidationError("This workout template is unavailable.")

    existing = list(
        TemplateExercise.objects
        .select_for_update()
        .filter(template=template)
        .order_by("position", "pk")
    )

    if entry.pk and not any(
        item.pk == entry.pk for item in existing
    ):
        raise ValidationError(
            "This exercise is no longer in the template."
        )

    others = [
        item for item in existing
        if item.pk != entry.pk
    ]

    if any(
        item.definition_id == entry.definition_id
        for item in others
    ):
        raise ValidationError(
            "This exercise is already in the template. "
            "Edit its existing entry instead."
        )

    if (
        entry.position is None
        or not 1 <= entry.position <= len(others) + 1
    ):
        raise ValidationError(
            "Choose a position within the exercise list."
        )

    entry.template = template

    # Validate fields and ownership before changing any saved positions.
    # Position uniqueness is handled by the transaction below.
    entry.full_clean(
        validate_unique=False,
        validate_constraints=False,
    )

    ordered = others.copy()
    ordered.insert(entry.position - 1, entry)

    # Temporarily move saved entries above all occupied positions.
    # This avoids collisions with the database's unique constraint.
    highest_position = max(
        (item.position for item in existing),
        default=0,
    )

    if highest_position + len(existing) > 32767:
        raise ValidationError(
            "The exercise order is too large to rearrange safely."
        )

    for offset, item in enumerate(existing, start=1):
        TemplateExercise.objects.filter(pk=item.pk).update(
            position=highest_position + offset,
        )

    # Save the final order as consecutive positions.
    for position, item in enumerate(ordered, start=1):
        item.position = position

        if item is entry:
            item.save()
        else:
            TemplateExercise.objects.filter(pk=item.pk).update(
                position=position,
            )

    return entry

@transaction.atomic
def reorder_template_exercises(*, template, user, ordered_ids):
    locked_template = (
        WorkoutTemplate.objects
        .select_for_update()
        .filter(pk=template.pk, routine__user=user)
        .first()
    )

    if locked_template is None:
        raise ValidationError("This workout template is unavailable.")

    existing = list(
        TemplateExercise.objects
        .select_for_update()
        .filter(template=locked_template)
        .order_by("position", "pk")
    )

    try:
        requested_ids = [int(value) for value in ordered_ids]
    except (TypeError, ValueError):
        raise ValidationError("The exercise order is invalid.") from None

    existing_ids = {item.pk for item in existing}

    if (
        len(requested_ids) != len(existing)
        or len(set(requested_ids)) != len(requested_ids)
        or set(requested_ids) != existing_ids
    ):
        raise ValidationError(
            "The exercise list changed. Refresh this page before "
            "reordering it again."
        )

    if requested_ids == [item.pk for item in existing]:
        return

    highest_position = max(
        (item.position for item in existing),
        default=0,
    )

    if highest_position + len(existing) > 32767:
        raise ValidationError(
            "The exercise order is too large to rearrange safely."
        )

    for offset, item in enumerate(existing, start=1):
        TemplateExercise.objects.filter(pk=item.pk).update(
            position=highest_position + offset,
        )

    for position, entry_id in enumerate(requested_ids, start=1):
        TemplateExercise.objects.filter(pk=entry_id).update(
            position=position,
        )