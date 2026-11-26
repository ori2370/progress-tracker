from datetime import datetime, timedelta

from django import forms
from django.utils import timezone


class SessionTimesForm(forms.Form):
    started_at = forms.DateTimeField(
        label="Start date and time",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local"},
        ),
    )
    finished_at = forms.DateTimeField(
        label="Finish date and time",
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local"},
        ),
    )
    duration_minutes = forms.IntegerField(
        label="Or duration in minutes",
        min_value=1,
        max_value=1440,
        required=False,
        help_text="Enter a finish time or a duration, not both.",
    )

    def __init__(self, *args, session, **kwargs):
        super().__init__(*args, **kwargs)

        if self.is_bound:
            return

        if session.started_at:
            self.initial["started_at"] = timezone.localtime(
                session.started_at
            )
        elif session.start_time:
            self.initial["started_at"] = timezone.make_aware(
                datetime.combine(session.date, session.start_time),
                timezone.get_current_timezone(),
            )

        if session.finished_at:
            self.initial["finished_at"] = timezone.localtime(
                session.finished_at
            )

    def clean(self):
        cleaned_data = super().clean()
        started = cleaned_data.get("started_at")
        finished = cleaned_data.get("finished_at")
        duration = cleaned_data.get("duration_minutes")

        if self.errors:
            return cleaned_data

        if finished is not None and duration is not None:
            raise forms.ValidationError(
                "Enter a finish time or a duration, not both."
            )

        if finished is None and duration is None:
            raise forms.ValidationError(
                "Enter a finish time or a duration."
            )

        if duration is not None:
            finished = started + timedelta(minutes=duration)

        if finished <= started:
            self.add_error(
                "finished_at",
                "Finish time must be after the start.",
            )
        elif finished > timezone.now():
            self.add_error(
                "finished_at",
                "Finish time cannot be in the future.",
            )

        cleaned_data["finished_at"] = finished
        return cleaned_data