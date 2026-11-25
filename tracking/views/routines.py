from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    UpdateView,
)
from django.db import transaction
from .gym import OwnedGymDataMixin
from ..forms.routines import (
    TemplateExerciseForm,
    WorkoutRoutineForm,
    WorkoutTemplateForm,
)
from ..models import (
    TemplateExercise,
    WorkoutRoutine,
    WorkoutTemplate,
)
from ..services.routines import (
    reorder_template_exercises,
    save_template_exercise,
)


class WorkoutRoutineListView(OwnedGymDataMixin, ListView):
    model = WorkoutRoutine
    template_name = "tracking/workout_routine_list.html"
    context_object_name = "routines"


class WorkoutRoutineCreateView(OwnedGymDataMixin, CreateView):
    model = WorkoutRoutine
    form_class = WorkoutRoutineForm
    template_name = "tracking/workout_routine_form.html"
    success_url = reverse_lazy("tracking:routine-list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class WorkoutRoutineUpdateView(OwnedGymDataMixin, UpdateView):
    model = WorkoutRoutine
    form_class = WorkoutRoutineForm
    template_name = "tracking/workout_routine_form.html"
    success_url = reverse_lazy("tracking:routine-list")


class WorkoutRoutineDetailView(OwnedGymDataMixin, DetailView):
    model = WorkoutRoutine
    template_name = "tracking/workout_routine_detail.html"
    context_object_name = "routine"

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            "templates__exercises__definition"
        )


class WorkoutTemplateCreateView(OwnedGymDataMixin, CreateView):
    model = WorkoutTemplate
    form_class = WorkoutTemplateForm
    template_name = "tracking/workout_template_form.html"

    def get_routine(self):
        if not hasattr(self, "_routine"):
            self._routine = get_object_or_404(
                WorkoutRoutine,
                pk=self.kwargs["routine_pk"],
                user=self.request.user,
            )

        return self._routine

    def get_queryset(self):
        return WorkoutTemplate.objects.filter(
            routine__user=self.request.user
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["routine"] = self.get_routine()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["routine"] = self.get_routine()
        return context

    def get_success_url(self):
        return reverse(
            "tracking:template-update",
            kwargs={"pk": self.object.pk},
        )


class WorkoutTemplateUpdateView(OwnedGymDataMixin, UpdateView):
    model = WorkoutTemplate
    form_class = WorkoutTemplateForm
    template_name = "tracking/workout_template_form.html"

    def get_queryset(self):
        return (
            WorkoutTemplate.objects
            .filter(routine__user=self.request.user)
            .select_related("routine")
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["routine"] = self.object.routine
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["routine"] = self.object.routine
        context["template_exercises"] = (
            self.object.exercises
            .select_related("definition")
            .order_by("position", "pk")
        )
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                reorder_template_exercises(
                    template=self.object,
                    user=self.request.user,
                    ordered_ids=self.request.POST.getlist(
                        "exercise_order"
                    ),
                )
                self.object = form.save()
        except ValidationError as error:
            for message in error.messages:
                form.add_error(None, message)

            return self.form_invalid(form)

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(
            "tracking:routine-detail",
            kwargs={"pk": self.object.routine_id},
        )


class TemplateExerciseSaveMixin:
    model = TemplateExercise
    form_class = TemplateExerciseForm
    template_name = "tracking/template_exercise_form.html"

    def form_valid(self, form):
        entry = form.save(commit=False)

        try:
            self.object = save_template_exercise(
                entry=entry,
                user=self.request.user,
            )
        except ValidationError as error:
            for message in error.messages:
                form.add_error(None, message)

            return self.form_invalid(form)

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(
            "tracking:template-update",
            kwargs={"pk": self.object.template_id},
        )


class TemplateExerciseCreateView(
    OwnedGymDataMixin,
    TemplateExerciseSaveMixin,
    CreateView,
):
    def get_template(self):
        if not hasattr(self, "_template"):
            self._template = get_object_or_404(
                WorkoutTemplate.objects.select_related("routine"),
                pk=self.kwargs["template_pk"],
                routine__user=self.request.user,
            )

        return self._template

    def get_queryset(self):
        return TemplateExercise.objects.filter(
            template__routine__user=self.request.user
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["template"] = self.get_template()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial["position"] = (
            self.get_template().exercises.count() + 1
        )
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["template"] = self.get_template()
        return context


class TemplateExerciseUpdateView(
    OwnedGymDataMixin,
    TemplateExerciseSaveMixin,
    UpdateView,
):
    def get_queryset(self):
        return (
            TemplateExercise.objects
            .filter(template__routine__user=self.request.user)
            .select_related("template__routine")
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["template"] = self.object.template
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["template"] = self.object.template
        return context