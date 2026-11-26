from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.core.exceptions import ValidationError
from ..services.workout_order import reorder_workout_exercises
from ..models import GymExercise, GymWorkout
from .gym import OwnedGymDataMixin


class WorkoutExerciseInclusionView(OwnedGymDataMixin, View):
    def post(self, request, exercise_pk):
        inclusion = request.POST.get("inclusion")

        if inclusion not in GymExercise.Inclusion.values:
            return HttpResponseBadRequest("Choose a valid exercise action.")

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

            if not workout.is_in_progress:
                return HttpResponseBadRequest(
                    "Exercise selection can only change during an ongoing workout."
                )

            if not exercise.copied_from_template:
                return HttpResponseBadRequest(
                    "This action applies only to exercises copied from a template."
                )

            if exercise.sets.exists():
                return HttpResponseBadRequest(
                    "This exercise already has recorded sets and cannot be skipped or hidden."
                )

            exercise.inclusion = inclusion
            exercise.save(update_fields=["inclusion"])

        return HttpResponseRedirect(
            reverse(
                "tracking:gym-workout-detail",
                kwargs={"pk": workout.pk},
            )
        )


class WorkoutExerciseOrderView(OwnedGymDataMixin, View):
    def post(self, request, workout_pk):
        try:
            reorder_workout_exercises(
                workout_pk=workout_pk,
                user=request.user,
                ordered_ids=request.POST.getlist("exercise_order"),
            )
        except ValidationError as error:
            return HttpResponseBadRequest(
                " ".join(error.messages),
                content_type="text/plain",
            )

        return HttpResponseRedirect(
            reverse(
                "tracking:gym-workout-detail",
                kwargs={"pk": workout_pk},
            )
        )

class CompletedExerciseInclusionView(OwnedGymDataMixin, View):
    def post(self, request, exercise_pk):
        inclusion = request.POST.get("inclusion")

        if inclusion not in GymExercise.Inclusion.values:
            return HttpResponseBadRequest(
                "Choose a valid exercise action."
            )

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

            if workout.is_in_progress:
                return HttpResponseBadRequest(
                    "Use the ongoing workout's exercise controls."
                )

            if exercise.sets.exists():
                return HttpResponseBadRequest(
                    "An exercise with recorded sets cannot be skipped or hidden."
                )

            exercise.inclusion = inclusion
            exercise.save(update_fields=["inclusion"])

        return HttpResponseRedirect(
            reverse(
                "tracking:gym-workout-detail",
                kwargs={"pk": workout.pk},
            )
        )