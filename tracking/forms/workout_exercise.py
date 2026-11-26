from django import forms


class WorkoutExerciseNoteForm(forms.Form):
    notes = forms.CharField(
        label="Exercise note",
        required=False,
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Warm-up, seat setting, technique reminder…",
            }
        ),
    )