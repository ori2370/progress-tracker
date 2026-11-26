from django import forms
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View
from ..services.weight_suggestions import previous_weight_sets
from ..forms.workout_sets import WorkoutSetFormSet
from ..models import GymExercise, GymSet
from .gym import OwnedGymDataMixin
from .gym_logging import ExerciseProgressMixin


class SetPlanForm(forms.Form):
    planned_sets = forms.IntegerField(
        label="Planned sets for this exercise",
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={"min": 1, "max": 20}),
    )


class WorkoutSetsView(
    OwnedGymDataMixin,
    ExerciseProgressMixin,
    View,
):
    template_name = "tracking/workout_sets_form.html"

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

    def editor_url(self):
        return reverse(
            "tracking:gym-sets-log",
            kwargs={"exercise_pk": self.get_exercise().pk},
        )

    def get_count(self):
        exercise = self.get_exercise()
        remaining = max(
            0,
            exercise.planned_sets - exercise.sets.count(),
        )

        source = (
            self.request.POST
            if self.request.method == "POST"
            else self.request.GET
        )

        if source.get("extra") == "1":
            return 1

        return min(20, remaining)

    def make_formset(self):
        return WorkoutSetFormSet(
            data=(
                self.request.POST
                if self.request.method == "POST"
                else None
            ),
            initial=[{} for _ in range(self.get_count())],
            prefix="sets",
            form_kwargs={"exercise": self.get_exercise()},
        )

    def render_editor(self, formset, plan_form=None, error=None):
        exercise = self.get_exercise()
        recorded = list(exercise.sets.all())
        can_set_legacy_weight_basis = (
            not exercise.workout.is_in_progress
            and bool(recorded)
            and all(
                entry.weight_basis == ""
                and entry.weight_kg is not None
                and entry.reps is not None
                and entry.duration_seconds is None
                for entry in recorded
            )
        )
        last_number = max(
            (entry.number for entry in recorded),
            default=0,
        )
        source = (
            self.request.POST
            if self.request.method == "POST"
            else self.request.GET
        )

        if plan_form is None:
            plan_form = SetPlanForm(
                initial={"planned_sets": exercise.planned_sets}
            )

        context = {
            "exercise": exercise,
            "formset": formset,
            "plan_form": plan_form,
            "editor_error": error,
            "recorded_sets": recorded,
            "recorded_count": len(recorded),
            "goal_reached": len(recorded) >= exercise.planned_sets,
            "extra_requested": source.get("extra") == "1",
            "last_recorded_set": recorded[-1] if recorded else None,
            "can_set_legacy_weight_basis": can_set_legacy_weight_basis,
            "set_rows": [
                {
                    "form": form,
                    "number": last_number + index + 1,
                }
                for index, form in enumerate(formset.forms)
            ],
        }
        context.update(self.get_progress_context(exercise))
        previous_sets = previous_weight_sets(exercise)
        previous_by_number = {
            entry.number: entry
            for entry in previous_sets
        }

        for row in context["set_rows"]:
            row["weight_suggestion"] = previous_by_number.get(
                row["number"]
            )
        return render(self.request, self.template_name, context)

    def get(self, request, *args, **kwargs):
        return self.render_editor(self.make_formset())

    def post(self, request, *args, **kwargs):
        exercise = self.get_exercise()

        if request.POST.get("action") == "plan":
            plan_form = SetPlanForm(request.POST)

            if not plan_form.is_valid():
                return self.render_editor(
                    self.make_formset(),
                    plan_form=plan_form,
                )

            with transaction.atomic():
                locked = get_object_or_404(
                    GymExercise.objects.select_for_update(),
                    pk=exercise.pk,
                    workout__user=request.user,
                )
                locked.planned_sets = plan_form.cleaned_data[
                    "planned_sets"
                ]
                locked.save(update_fields=["planned_sets"])

            return HttpResponseRedirect(self.editor_url())

        formset = self.make_formset()

        if not formset.is_valid():
            return self.render_editor(formset)

        filled_forms = [
            form for form in formset.forms
            if form.has_changed()
        ]

        with transaction.atomic():
            locked = get_object_or_404(
                GymExercise.objects.select_for_update(),
                pk=exercise.pk,
                workout__user=request.user,
            )

            last_number = (
                locked.sets.aggregate(last=Max("number"))["last"]
                or 0
            )

            if last_number + len(filled_forms) > 32767:
                return self.render_editor(
                    formset,
                    error="This exercise has reached the maximum number of sets.",
                )

            for form in filled_forms:
                last_number += 1
                data = form.cleaned_data

                entry = GymSet(
                    exercise=locked,
                    number=last_number,
                    reps=data.get("reps"),
                    weight_kg=data.get("weight_kg"),
                    weight_basis=data.get("weight_basis", ""),
                    duration_seconds=data.get("duration_seconds"),
                )
                entry.full_clean()
                entry.save()

        return HttpResponseRedirect(self.editor_url())