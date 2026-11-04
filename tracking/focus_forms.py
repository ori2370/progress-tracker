from django import forms

from .models import TennisFocus


class TennisFocusForm(forms.ModelForm):
    class Meta:
        model = TennisFocus
        fields = [
            "title",
            "goal",
            "start_date",
            "end_date",
            "target_sessions",
        ]
        labels = {
            "title": "What are you working on?",
            "goal": "What do you want to improve?",
            "target_sessions": "Session target (optional)",
        }
        help_texts = {
            "title": "For example: backhand consistency or serve placement.",
            "target_sessions": "Leave blank to track the date range only.",
        }
        widgets = {
            "goal": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "target_sessions": forms.NumberInput(attrs={"min": 1}),
        }