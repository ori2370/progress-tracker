from django import forms
from django.forms import BaseFormSet, formset_factory

from ..models import ExerciseTrackingMode, GymSet

class WorkoutSetRowForm(forms.Form):
    reps = forms.IntegerField(
        min_value=1,
        required=False,
        widget=forms.NumberInput(attrs={"min": 1}),
    )
    weight_kg = forms.DecimalField(
        label="Weight (kg)",
        min_value=0,
        max_digits=6,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(
            attrs={"min": 0, "step": "0.01"}
        ),
    )
    weight_basis = forms.ChoiceField(
        label="Weight basis",
        choices=[
            (GymSet.WeightBasis.TOTAL, "Total"),
            (GymSet.WeightBasis.PER_SIDE, "Per side"),
            (GymSet.WeightBasis.PER_DUMBBELL, "Per dumbbell"),
        ],
        initial=GymSet.WeightBasis.TOTAL,
        required=False,
    )
    minutes = forms.IntegerField(
        min_value=0,
        max_value=1440,
        required=False,
        widget=forms.NumberInput(attrs={"min": 0, "max": 1440}),
    )
    seconds = forms.IntegerField(
        min_value=0,
        max_value=59,
        required=False,
        widget=forms.NumberInput(attrs={"min": 0, "max": 59}),
    )

    def __init__(self, *args, exercise, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_timed = (
            exercise.tracking_mode == ExerciseTrackingMode.DURATION
        )

        if self.is_timed:
            self.fields.pop("reps")
            self.fields.pop("weight_kg")
            self.fields.pop("weight_basis")
        else:
            self.fields.pop("minutes")
            self.fields.pop("seconds")
    def has_changed(self):
        return any(
            name != "weight_basis"
            for name in self.changed_data
        )
    def clean(self):
        cleaned = super().clean()

        if self.errors:
            return cleaned

        if self.is_timed:
            minutes = cleaned.get("minutes")
            seconds = cleaned.get("seconds")

            if minutes is None and seconds is None:
                return cleaned

            duration = (minutes or 0) * 60 + (seconds or 0)

            if duration <= 0:
                raise forms.ValidationError(
                    "Enter a duration greater than zero."
                )

            cleaned["duration_seconds"] = duration
        else:
            reps = cleaned.get("reps")
            weight = cleaned.get("weight_kg")
            cleaned["weight_basis"] = (
                cleaned.get("weight_basis")
                or GymSet.WeightBasis.TOTAL
            )
            if reps is None and weight is None:
                return cleaned

            if reps is None:
                self.add_error("reps", "Enter the reps for this set.")

            if weight is None:
                self.add_error(
                    "weight_kg",
                    "Enter the weight, or 0 for bodyweight.",
                )

        return cleaned


class BaseWorkoutSetFormSet(BaseFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        if not any(form.has_changed() for form in self.forms):
            raise forms.ValidationError(
                "Fill at least one set before saving."
            )


WorkoutSetFormSet = formset_factory(
    WorkoutSetRowForm,
    formset=BaseWorkoutSetFormSet,
    extra=0,
    max_num=20,
    validate_max=True,
    absolute_max=20,
)