from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, UpdateView

from .gym_forms import GymSetForm
from .gym_views import OwnedGymDataMixin
from .models import GymExercise, GymSet


class ExerciseProgressMixin:
    def get_progress_context(self, exercise):
        definition = exercise.definition

        if definition is None:
            return {}

        today = timezone.localdate()

        # Compare against workouts dated no later than this workout.
        cutoff = min(today, exercise.workout.date)

        previous = (
            GymExercise.objects.filter(
                definition=definition,
                workout__user=self.request.user,
                workout__date__lte=cutoff,
                sets__isnull=False,
            )
            .exclude(workout_id=exercise.workout_id)
            .select_related("workout")
            .prefetch_related("sets")
            .distinct()
            .order_by(
                "-workout__date",
                "-workout__start_time",
                "-workout__created_at",
                "-pk",
            )
            .first()
        )

        personal_best = (
            GymSet.objects.filter(
                exercise__definition=definition,
                exercise__workout__user=self.request.user,
                exercise__workout__date__lte=today,
            )
            .select_related("exercise__workout")
            .order_by(
                "-weight_kg",
                "-reps",
                "-exercise__workout__date",
                "-pk",
            )
            .first()
        )

        return {
            "exercise_definition": definition,
            "previous_performance": previous,
            "personal_best": personal_best,
        }


class GymSetCreateView(
    OwnedGymDataMixin,
    ExerciseProgressMixin,
    CreateView,
):
    model = GymSet
    form_class = GymSetForm
    template_name = "tracking/gym_set_form.html"

    def get_queryset(self):
        return GymSet.objects.filter(
            exercise__workout__user=self.request.user
        )

    def get_exercise(self):
        if not hasattr(self, "_exercise"):
            self._exercise = get_object_or_404(
                GymExercise.objects.select_related(
                    "workout",
                    "definition",
                ),
                pk=self.kwargs["exercise_pk"],
                workout__user=self.request.user,
            )

        return self._exercise

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exercise = self.get_exercise()

        context["exercise"] = exercise
        context["recorded_sets"] = exercise.sets.all()
        context.update(self.get_progress_context(exercise))

        return context

    def form_valid(self, form):
        exercise = self.get_exercise()

        with transaction.atomic():
            GymExercise.objects.select_for_update().get(pk=exercise.pk)

            last_number = exercise.sets.aggregate(
                last=Max("number")
            )["last"]

            form.instance.exercise = exercise
            form.instance.number = (last_number or 0) + 1

            return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "tracking:gym-set-create",
            kwargs={"exercise_pk": self.get_exercise().pk},
        )


class GymSetUpdateView(
    OwnedGymDataMixin,
    ExerciseProgressMixin,
    UpdateView,
):
    model = GymSet
    form_class = GymSetForm
    template_name = "tracking/gym_set_form.html"

    def get_queryset(self):
        return GymSet.objects.filter(
            exercise__workout__user=self.request.user
        ).select_related(
            "exercise__workout",
            "exercise__definition",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exercise = self.object.exercise

        context["exercise"] = exercise
        context["recorded_sets"] = exercise.sets.all()
        context.update(self.get_progress_context(exercise))

        return context

    def get_success_url(self):
        return reverse(
            "tracking:gym-set-create",
            kwargs={"exercise_pk": self.object.exercise_id},
        )