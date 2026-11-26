from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View

from ..models import GymExercise, GymSet, GymWorkout
from .gym import OwnedGymDataMixin


class LegacyExerciseWeightBasisView(OwnedGymDataMixin, View):
    def post(self, request, exercise_pk):
        basis = request.POST.get("weight_basis")
        allowed = {
            GymSet.WeightBasis.TOTAL,
            GymSet.WeightBasis.PER_SIDE,
            GymSet.WeightBasis.PER_DUMBBELL,
        }

        if basis not in allowed:
            return HttpResponseBadRequest("Choose a valid weight basis.")

        with transaction.atomic():
            exercise = get_object_or_404(
                GymExercise,
                pk=exercise_pk,
                workout__user=request.user,
            )

            workout = get_object_or_404(
                GymWorkout.objects.select_for_update(),
                pk=exercise.workout_id,
                user=request.user,
            )

            exercise = get_object_or_404(
                GymExercise.objects.select_for_update(),
                pk=exercise_pk,
                workout=workout,
            )

            sets = list(
                GymSet.objects.select_for_update()
                .filter(exercise=exercise)
            )

            eligible = (
                not workout.is_in_progress
                and bool(sets)
                and all(
                    entry.weight_basis == ""
                    and entry.weight_kg is not None
                    and entry.reps is not None
                    and entry.duration_seconds is None
                    for entry in sets
                )
            )

            if not eligible:
                return HttpResponseBadRequest(
                    "This option applies only to completed exercises "
                    "whose strength sets all have no recorded weight basis."
                )

            GymSet.objects.filter(
                pk__in=[entry.pk for entry in sets]
            ).update(weight_basis=basis)

        return HttpResponseRedirect(
            reverse(
                "tracking:gym-sets-log",
                kwargs={"exercise_pk": exercise.pk},
            )
        )