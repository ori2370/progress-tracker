from django.urls import reverse_lazy,reverse
from django.views.generic import CreateView, ListView, UpdateView

from .gym_views import OwnedGymDataMixin
from .models import WorkoutRoutine,WorkoutTemplate,TemplateExercise
from .routine_forms import WorkoutRoutineForm,WorkoutTemplateForm,TemplateExerciseForm
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView
from django.db.models import Max



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
            "tracking:routine-detail",
            kwargs={"pk": self.get_routine().pk},
        )


class WorkoutTemplateUpdateView(OwnedGymDataMixin, UpdateView):
    model = WorkoutTemplate
    form_class = WorkoutTemplateForm
    template_name = "tracking/workout_template_form.html"

    def get_queryset(self):
        return WorkoutTemplate.objects.filter(
            routine__user=self.request.user
        ).select_related("routine")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["routine"] = self.object.routine
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["routine"] = self.object.routine
        return context

    def get_success_url(self):
        return reverse(
            "tracking:routine-detail",
            kwargs={"pk": self.object.routine_id},
        )

class TemplateExerciseCreateView(OwnedGymDataMixin, CreateView):
    model = TemplateExercise
    form_class = TemplateExerciseForm
    template_name = "tracking/template_exercise_form.html"

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
        last_position = self.get_template().exercises.aggregate(
            last=Max("position")
        )["last"]

        initial["position"] = (last_position or 0) + 1
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["template"] = self.get_template()
        return context

    def get_success_url(self):
        return reverse(
            "tracking:routine-detail",
            kwargs={"pk": self.get_template().routine_id},
        )


class TemplateExerciseUpdateView(OwnedGymDataMixin, UpdateView):
    model = TemplateExercise
    form_class = TemplateExerciseForm
    template_name = "tracking/template_exercise_form.html"

    def get_queryset(self):
        return TemplateExercise.objects.filter(
            template__routine__user=self.request.user
        ).select_related("template__routine")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["template"] = self.object.template
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["template"] = self.object.template
        return context

    def get_success_url(self):
        return reverse(
            "tracking:routine-detail",
            kwargs={"pk": self.object.template.routine_id},
        )