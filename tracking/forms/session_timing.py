from datetime import datetime, timedelta

from django import forms
from django.utils import timezone


class SessionTimingFormMixin(forms.Form):
    recording_mode = forms.ChoiceField(
        label="Record this session as",
        choices=[
            ("live", "Start now"),
            ("completed", "Already completed"),
        ],
        initial="live",
        required=False,
        help_text=(
            "Start now begins the timer when you save. "
            "Already completed uses the date and time entered below."
        ),
    )
    duration_minutes = forms.IntegerField(
        label="Completed duration (minutes)",
        min_value=1,
        max_value=1440,
        required=False,
        help_text=(
            "For completed sessions only. "
            "Enter a start time to record a duration."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.is_bound and not self.instance.pk:
            self.initial.setdefault("date", timezone.localdate())

        field_order = [
            "session_type",
            "recording_mode",
            "date",
            "start_time",
            "duration_minutes",
        ]
        self.order_fields(field_order)

    def clean(self):
        cleaned_data = super().clean()

        # Older clients that omit this field retain completed-entry behavior.
        mode = cleaned_data.get("recording_mode") or "completed"
        duration = cleaned_data.get("duration_minutes")

        if mode == "live":
            if duration is not None:
                self.add_error(
                    "duration_minutes",
                    "Leave duration blank when starting a live session.",
                )
                return cleaned_data

            now = timezone.now()
            local_now = timezone.localtime(now)

            cleaned_data["date"] = local_now.date()
            cleaned_data["start_time"] = (
                local_now.time().replace(tzinfo=None)
            )

            self.instance.status = self.instance.Status.IN_PROGRESS
            self.instance.started_at = now
            self.instance.finished_at = None

            return cleaned_data

        self.instance.status = self.instance.Status.COMPLETED
        self.instance.started_at = None
        self.instance.finished_at = None

        date = cleaned_data.get("date")
        start_time = cleaned_data.get("start_time")

        if duration is not None and start_time is None:
            self.add_error(
                "start_time",
                "Enter the start time for this duration.",
            )

        if date is not None and start_time is not None:
            started_at = timezone.make_aware(
                datetime.combine(date, start_time),
                timezone.get_current_timezone(),
            )
            self.instance.started_at = started_at

            if duration is not None:
                self.instance.finished_at = (
                    started_at + timedelta(minutes=duration)
                )

        return cleaned_data