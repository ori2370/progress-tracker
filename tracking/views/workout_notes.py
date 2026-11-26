from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView

from ..forms.workout_exercise import WorkoutExerciseNoteForm
from ..models import GymExercise
from .gym import OwnedGymDataMixin


class WorkoutExerciseNoteView(OwnedGymDataMixin, FormView):
    form_class = WorkoutExerciseNoteForm
    template_name = "tracking/workout_exercise_note_form.html"

    def get_exercise(self):
        if not hasattr(self, "_exercise"):
            self._exercise = get_object_or_404(
                GymExercise.objects.select_related("workout"),
                pk=self.kwargs["exercise_pk"],
                workout__user=self.request.user,
            )

        return self._exercise

    def get_initial(self):
        return {"notes": self.get_exercise().notes}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["exercise"] = self.get_exercise()
        return context

    def form_valid(self, form):
        with transaction.atomic():
            exercise = get_object_or_404(
                GymExercise.objects.select_for_update(),
                pk=self.kwargs["exercise_pk"],
                workout__user=self.request.user,
            )
            exercise.notes = form.cleaned_data["notes"]
            exercise.save(update_fields=["notes"])

        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "tracking:gym-sets-log",
            kwargs={"exercise_pk": self.get_exercise().pk},
        )