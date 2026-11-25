from django import forms

from ..models import (
    ExerciseDefinition,
    ExerciseTrackingMode,
    TemplateExercise,
    WorkoutRoutine,
    WorkoutTemplate,
)


class WorkoutRoutineForm(forms.ModelForm):
    class Meta:
        model = WorkoutRoutine
        fields = ["name", "sessions_per_week", "notes"]
        labels = {
            "name": "Routine name",
            "sessions_per_week": "Sessions per week",
        }
        widgets = {
            "sessions_per_week": forms.NumberInput(
                attrs={"min": 1, "max": 7}
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class WorkoutTemplateForm(forms.ModelForm):
    class Meta:
        model = WorkoutTemplate
        fields = ["name", "notes"]
        labels = {"name": "Workout name"}
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, routine, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.routine = routine

    def clean_name(self):
        name = self.cleaned_data["name"]
        duplicates = WorkoutTemplate.objects.filter(
            routine=self.instance.routine,
            name=name,
        )

        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)

        if duplicates.exists():
            raise forms.ValidationError(
                "This routine already has a template with that name."
            )

        return name


class ExerciseModeSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, **kwargs):
        option = super().create_option(
            name, value, label, selected, index, **kwargs
        )

        if hasattr(value, "instance"):
            option["attrs"]["data-tracking-mode"] = (
                value.instance.tracking_mode
            )

        return option


class TemplateExerciseForm(forms.ModelForm):
    target_minutes = forms.IntegerField(
        label="Target minutes",
        min_value=0,
        max_value=1440,
        required=False,
        widget=forms.NumberInput(attrs={"min": 0, "max": 1440}),
    )
    target_seconds = forms.IntegerField(
        label="Additional seconds",
        min_value=0,
        max_value=59,
        required=False,
        widget=forms.NumberInput(attrs={"min": 0, "max": 59}),
    )

    class Meta:
        model = TemplateExercise
        fields = [
            "definition",
            "position",
            "planned_sets",
            "target_reps",
            "target_minutes",
            "target_seconds",
        ]
        labels = {
            "definition": "Exercise",
            "position": "Order in workout",
            "planned_sets": "Sets / repetitions of the activity",
            "target_reps": "Target reps per set",
        }
        help_texts = {
            "position": "Other exercises move to make room.",
        }
        widgets = {
            "definition": ExerciseModeSelect(),
            "position": forms.NumberInput(attrs={"min": 1}),
            "planned_sets": forms.NumberInput(attrs={"min": 1}),
            "target_reps": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, template, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.template = template

        other_entries = template.exercises.all()
        if self.instance.pk:
            other_entries = other_entries.exclude(pk=self.instance.pk)

        used_definitions = other_entries.values_list(
            "definition_id",
            flat=True,
        )

        self.fields["definition"].queryset = (
            ExerciseDefinition.objects.filter(user=user)
            .exclude(pk__in=used_definitions)
        )
        self.fields["definition"].error_messages["invalid_choice"] = (
            "Choose an available exercise. If it is already in this "
            "template, edit its existing entry instead."
        )

        maximum_position = other_entries.count() + 1
        self.fields["position"].max_value = maximum_position
        self.fields["position"].widget.attrs["max"] = maximum_position

        if not self.is_bound:
            self.initial.setdefault("position", maximum_position)

            if self.instance.target_duration_seconds:
                minutes, seconds = divmod(
                    self.instance.target_duration_seconds,
                    60,
                )
                self.initial["target_minutes"] = minutes
                self.initial["target_seconds"] = seconds

    def clean(self):
        cleaned_data = super().clean()
        definition = cleaned_data.get("definition")
        position = cleaned_data.get("position")

        other_entries = self.instance.template.exercises.all()
        if self.instance.pk:
            other_entries = other_entries.exclude(pk=self.instance.pk)

        if position and position > other_entries.count() + 1:
            self.add_error(
                "position",
                "Choose a position within the exercise list.",
            )

        if not definition:
            return cleaned_data

        if other_entries.filter(definition=definition).exists():
            self.add_error(
                "definition",
                "This exercise is already in the template.",
            )
            return cleaned_data

        minutes = cleaned_data.get("target_minutes") or 0
        seconds = cleaned_data.get("target_seconds") or 0

        if definition.tracking_mode == ExerciseTrackingMode.DURATION:
            cleaned_data["target_reps"] = None
            self.instance.target_reps = None

            if (
                "target_minutes" not in self.errors
                and "target_seconds" not in self.errors
            ):
                duration = minutes * 60 + seconds
                self.instance.target_duration_seconds = duration or None
        else:
            self.instance.target_duration_seconds = None

            if minutes or seconds:
                self.add_error(
                    "target_minutes",
                    "Duration targets apply only to duration exercises.",
                )

        return cleaned_data