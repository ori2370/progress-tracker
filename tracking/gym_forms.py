from django import forms
from django.utils import timezone

from .models import BodyMeasurement, GymWorkout,ExerciseDefinition,GymSet,GymExercise

class BodyMeasurementForm(forms.ModelForm):
    class Meta:
        model = BodyMeasurement
        fields = ["date", "weight_kg", "waist_cm"]
        labels = {
            "weight_kg": "Bodyweight (kg)",
            "waist_cm": "Waist circumference (cm)",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "weight_kg": forms.NumberInput(
                attrs={"min": "0.01", "step": "0.01"}
            ),
            "waist_cm": forms.NumberInput(
                attrs={"min": "0.01", "step": "0.01"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.is_bound and not self.instance.pk:
            self.initial.setdefault("date", timezone.localdate())

class GymWorkoutForm(forms.ModelForm):
    class Meta:
        model = GymWorkout
        fields = ["date", "start_time", "title", "notes"]
        labels = {
            "title": "Workout name",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "time"},
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.is_bound and not self.instance.pk:
            self.initial.setdefault("date", timezone.localdate())

class ExerciseDefinitionForm(forms.ModelForm):
    class Meta:
        model = ExerciseDefinition
        fields = [
            "name",
            "equipment",
            "notes",
            "goal_weight_kg",
            "goal_reps",
        ]
        labels = {
            "name": "Exercise name",
            "equipment": "Equipment / machine",
            "goal_weight_kg": "Goal weight (kg)",
            "goal_reps": "Goal reps",
        }
        help_texts = {
            "equipment": "Useful for distinguishing different machines.",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "goal_weight_kg": forms.NumberInput(
                attrs={"min": "0", "step": "0.25"}
            ),
            "goal_reps": forms.NumberInput(attrs={"min": "1"}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.user = user

class GymSetForm(forms.ModelForm):
    class Meta:
        model = GymSet
        fields = ["reps", "weight_kg"]
        labels = {
            "reps": "Reps",
            "weight_kg": "Weight (kg)",
        }
        help_texts = {
            "weight_kg": "Use 0 for bodyweight only.",
        }
        widgets = {
            "reps": forms.NumberInput(attrs={"min": 1}),
            "weight_kg": forms.NumberInput(
                attrs={"min": "0", "step": "0.01"}
            ),
        }

class GymExerciseForm(forms.ModelForm):
    new_name = forms.CharField(
        label="New exercise / activity",
        max_length=150,
        required=False,
    )
    save_to_library = forms.BooleanField(
        label="Save new exercise to my library",
        required=False,
    )

    class Meta:
        model = GymExercise
        fields = ["definition"]
        labels = {
            "definition": "From your library",
        }

    def __init__(self, *args, user, workout, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.workout = workout

        self.fields["definition"].required = False
        self.fields["definition"].queryset = (
            ExerciseDefinition.objects.filter(user=user)
        )

    def clean(self):
        cleaned_data = super().clean()
        definition = cleaned_data.get("definition")
        new_name = cleaned_data.get("new_name", "")
        save_to_library = cleaned_data.get("save_to_library")

        if definition and new_name:
            raise forms.ValidationError(
                "Choose a library exercise or enter a new name, not both."
            )

        if not definition and not new_name:
            raise forms.ValidationError(
                "Choose an exercise or enter a new activity name."
            )

        if save_to_library and not new_name:
            self.add_error(
                "save_to_library",
                "Enter a new exercise name to save."
            )

        return cleaned_data