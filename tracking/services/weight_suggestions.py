from django.db.models import Q

from ..models import ExerciseTrackingMode, GymExercise, GymSet, GymWorkout


def previous_weight_sets(exercise):
    if (
        not exercise.definition_id
        or exercise.tracking_mode != ExerciseTrackingMode.STRENGTH
    ):
        return []

    earlier = (
        Q(workout__date__lt=exercise.workout.date)
        | Q(
            workout__date=exercise.workout.date,
            workout__created_at__lt=exercise.workout.created_at,
        )
    )

    previous = (
        GymExercise.objects.filter(
            earlier,
            definition_id=exercise.definition_id,
            workout__user_id=exercise.workout.user_id,
            workout__status=GymWorkout.Status.COMPLETED,
            tracking_mode=ExerciseTrackingMode.STRENGTH,
            sets__isnull=False,
        )
        .exclude(workout_id=exercise.workout_id)
        .select_related("workout")
        .distinct()
        .order_by(
            "-workout__date",
            "-workout__created_at",
            "-pk",
        )
        .first()
    )

    if previous is None:
        return []

    return list(
        previous.sets.filter(
            weight_kg__isnull=False,
            duration_seconds__isnull=True,
            weight_basis__in=[
                GymSet.WeightBasis.TOTAL,
                GymSet.WeightBasis.PER_SIDE,
                GymSet.WeightBasis.PER_DUMBBELL,
            ],
        )
    )