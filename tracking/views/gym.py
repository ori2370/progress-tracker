from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, Q, Max
from django.urls import reverse_lazy,reverse
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView, DetailView,TemplateView,DeleteView
from ..forms.gym import BodyMeasurementForm, GymWorkoutForm,ExerciseDefinitionForm
from ..models import BodyMeasurement, ExerciseTrackingMode, GymWorkout,ExerciseDefinition,GymExercise,WorkoutTemplate,CatalogExercise
from django.db import transaction
from django.shortcuts import get_object_or_404
from ..forms.gym import GymExerciseForm

class OwnedGymDataMixin(LoginRequiredMixin):
    login_url = "/account/login/"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class BodyMeasurementListView(OwnedGymDataMixin, ListView):
    model = BodyMeasurement
    template_name = "tracking/body_measurement_list.html"
    context_object_name = "measurements"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = timezone.localdate()
        current_start = today - timedelta(days=6)
        previous_start = today - timedelta(days=13)
        previous_end = today - timedelta(days=7)

        measurements = self.get_queryset()

        current_period = Q(date__range=(current_start, today))
        previous_period = Q(
            date__range=(previous_start, previous_end)
        )

        summary = measurements.aggregate(
            current_average=Avg("weight_kg", filter=current_period),
            current_count=Count("weight_kg", filter=current_period),
            previous_average=Avg("weight_kg", filter=previous_period),
            previous_count=Count("weight_kg", filter=previous_period),
        )

        context.update(summary)
        context["current_start"] = current_start
        context["current_end"] = today
        context["previous_start"] = previous_start
        context["previous_end"] = previous_end

        current_average = summary["current_average"]
        previous_average = summary["previous_average"]

        if current_average is not None and previous_average is not None:
            change = (current_average - previous_average).quantize(
                Decimal("0.01")
            )
            context["weight_comparison_available"] = True
            context["weight_change_display"] = f"{change:+.2f}"
            context["weight_direction"] = self.get_direction(change)

        waist_records = list(
            measurements.filter(
                waist_cm__isnull=False,
                date__lte=today,
            ).order_by("-date", "-created_at", "-pk")[:2]
        )

        if waist_records:
            context["latest_waist"] = waist_records[0]

        if len(waist_records) == 2:
            latest, previous = waist_records
            change = latest.waist_cm - previous.waist_cm

            context["previous_waist"] = previous
            context["waist_change_display"] = f"{change:+.2f}"
            context["waist_direction"] = self.get_direction(change)

        return context

    @staticmethod
    def get_direction(change):
        if change > 0:
            return "Increase"
        if change < 0:
            return "Decrease"
        return "No change"


class BodyMeasurementCreateView(OwnedGymDataMixin, CreateView):
    model = BodyMeasurement
    form_class = BodyMeasurementForm
    template_name = "tracking/body_measurement_form.html"
    success_url = reverse_lazy("tracking:measurement-list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class BodyMeasurementUpdateView(OwnedGymDataMixin, UpdateView):
    model = BodyMeasurement
    form_class = BodyMeasurementForm
    template_name = "tracking/body_measurement_form.html"
    success_url = reverse_lazy("tracking:measurement-list")


class GymWorkoutListView(OwnedGymDataMixin, ListView):
    model = GymWorkout
    template_name = "tracking/gym_workout_list.html"
    context_object_name = "workouts"
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().prefetch_related("exercises__sets")


class GymWorkoutCreateView(OwnedGymDataMixin, CreateView):
    model = GymWorkout
    form_class = GymWorkoutForm
    template_name = "tracking/gym_workout_form.html"
    success_url = reverse_lazy("tracking:gym-workout-list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class ExerciseDefinitionListView(OwnedGymDataMixin, ListView):
    model = ExerciseDefinition
    template_name = "tracking/exercise_definition_list.html"
    context_object_name = "exercises"
    paginate_by = 20


class ExerciseDefinitionFormMixin:
    model = ExerciseDefinition
    form_class = ExerciseDefinitionForm
    template_name = "tracking/exercise_definition_form.html"
    success_url = reverse_lazy("tracking:exercise-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class ExerciseDefinitionCreateView(
    OwnedGymDataMixin,
    ExerciseDefinitionFormMixin,
    CreateView,
):
    def get_catalog_exercise(self):
        catalog_id = self.request.GET.get("catalog")

        if not catalog_id:
            return None

        if not hasattr(self, "_catalog_exercise"):
            self._catalog_exercise = get_object_or_404(
                CatalogExercise,
                pk=catalog_id,
            )

        return self._catalog_exercise

    def get_initial(self):
        initial = super().get_initial()
        catalog = self.get_catalog_exercise()

        if catalog:
            initial.update({
                "name": catalog.name,
                "equipment": catalog.equipment,
            })

        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        catalog = self.get_catalog_exercise()

        if catalog:
            instance = self.model(
                user=self.request.user,
                catalog_exercise=catalog,
            )
            kwargs["instance"] = instance

        return kwargs

    def get_success_url(self):
        return reverse("tracking:exercise-list")


class ExerciseDefinitionUpdateView(
    OwnedGymDataMixin,
    ExerciseDefinitionFormMixin,
    UpdateView,
):
    def get_success_url(self):
        if self.request.POST.get("stay_on_form") == "1":
            return reverse(
                "tracking:exercise-update",
                kwargs={"pk": self.object.pk},
            )

        return super().get_success_url()

class GymWorkoutDetailView(OwnedGymDataMixin, DetailView):
    model = GymWorkout
    template_name = "tracking/gym_workout_detail.html"
    context_object_name = "workout"

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            "exercises__sets"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exercises = list(self.object.exercises.all())

        recorded_exercises = 0
        recorded_sets = 0
        skipped_exercises = 0
        visible_exercises = []

        for exercise in exercises:
            sets = list(exercise.sets.all())
            exercise.recorded_set_count = len(sets)

            if exercise.inclusion == "omitted":
                continue

            visible_exercises.append(exercise)
            recorded_sets += len(sets)

            if sets:
                recorded_exercises += 1

            if exercise.inclusion == "skipped":
                skipped_exercises += 1

        context.update({
            "visible_exercises": visible_exercises,
            "recorded_exercise_count": recorded_exercises,
            "recorded_set_count": recorded_sets,
            "skipped_exercise_count": skipped_exercises,
        })

        return context


class GymWorkoutFromTemplateView(OwnedGymDataMixin, CreateView):
    model = GymWorkout
    form_class = GymWorkoutForm
    template_name = "tracking/gym_workout_start.html"

    def get_template(self):
        if not hasattr(self, "_template"):
            self._template = get_object_or_404(
                WorkoutTemplate.objects.select_related(
                    "routine"
                ).prefetch_related("exercises__definition"),
                pk=self.kwargs["template_pk"],
                routine__user=self.request.user,
            )

        return self._template

    def get_initial(self):
        initial = super().get_initial()
        initial["title"] = self.get_template().name
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["template"] = self.get_template()
        return context

    def form_valid(self, form):
        template = self.get_template()
        entries = list(template.exercises.all())

        if not entries:
            form.add_error(
                None,
                "Add at least one exercise to this template first.",
            )
            return self.form_invalid(form)

        if any(
            entry.definition.user_id != self.request.user.pk
            for entry in entries
        ):
            form.add_error(
                None,
                "This template contains an unavailable exercise.",
            )
            return self.form_invalid(form)

        with transaction.atomic():
            form.instance.user = self.request.user
            form.instance.source_template = template
            response = super().form_valid(form)

            GymExercise.objects.bulk_create([
                GymExercise(
                    workout=self.object,
                    definition=entry.definition,
                    name=str(entry.definition),
                    tracking_mode=entry.definition.tracking_mode,
                    position=entry.position,
                    planned_sets=entry.planned_sets,
                    copied_from_template=True,
                )
                for entry in entries
            ])

        return response

    def get_success_url(self):
        return reverse(
            "tracking:gym-workout-detail",
            kwargs={"pk": self.object.pk},
        )


class GymWorkoutChooseView(OwnedGymDataMixin, TemplateView):
    template_name = "tracking/gym_workout_choose.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["templates"] = (
            WorkoutTemplate.objects.filter(
                routine__user=self.request.user
            )
            .select_related("routine")
            .order_by("routine__name", "name", "pk")
        )

        return context


class GymExerciseCreateView(OwnedGymDataMixin, CreateView):
    model = GymExercise
    form_class = GymExerciseForm
    template_name = "tracking/gym_exercise_form.html"

    def get_queryset(self):
        return GymExercise.objects.filter(
            workout__user=self.request.user
        )

    def get_workout(self):
        if not hasattr(self, "_workout"):
            self._workout = get_object_or_404(
                GymWorkout,
                pk=self.kwargs["workout_pk"],
                user=self.request.user,
            )

        return self._workout

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["workout"] = self.get_workout()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workout"] = self.get_workout()
        return context

    def form_valid(self, form):
        workout = self.get_workout()
        definition = form.cleaned_data.get("definition")
        new_name = form.cleaned_data["new_name"]
        selected_mode = (
            form.cleaned_data.get("tracking_mode")
            or ExerciseTrackingMode.STRENGTH
        )

        with transaction.atomic():
            GymWorkout.objects.select_for_update().get(pk=workout.pk)

            if new_name and form.cleaned_data["save_to_library"]:
                definition, created = (
                    ExerciseDefinition.objects.get_or_create(
                        user=self.request.user,
                        name=new_name,
                        equipment="",
                        defaults={"tracking_mode": selected_mode},
                    )
                )

                if not created and definition.tracking_mode != selected_mode:
                    form.add_error(
                        "new_name",
                        "A library exercise with this name uses a different "
                        "logging mode. Choose it above or use a different name.",
                    )
                    return self.form_invalid(form)

            last_position = workout.exercises.aggregate(
                last=Max("position")
            )["last"]

            form.instance.position = (last_position or 0) + 1
            form.instance.definition = definition
            form.instance.tracking_mode = (
                definition.tracking_mode
                if definition
                else selected_mode
            )
            form.instance.name = (
                str(definition) if definition else new_name
            )

            return super().form_valid(form)
    def get_success_url(self):
        return reverse(
            "tracking:gym-workout-detail",
            kwargs={"pk": self.get_workout().pk},
        )


class GymWorkoutDeleteView(OwnedGymDataMixin, DeleteView):
    model = GymWorkout
    template_name = "tracking/gym_workout_confirm_delete.html"
    context_object_name = "workout"
    success_url = reverse_lazy("tracking:gym-workout-list")