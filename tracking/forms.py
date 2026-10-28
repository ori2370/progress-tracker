from django import forms

from .models import TennisSession


class TennisSessionForm(forms.ModelForm):
    class Meta:
        model = TennisSession
        fields = [
            "date",
            "session_type",
            "focus",
            "notes",
            "coach_feedback",
            "next_practice_goal",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "coach_feedback": forms.Textarea(attrs={"rows": 3}),
        }