from django import forms
from django.utils import timezone


class SessionFinishForm(forms.Form):
    finish_mode = forms.ChoiceField(
        label="When did you finish?",
        choices=[
            ("now", "Finish now"),
            ("custom", "Choose an earlier finish time"),
        ],
        initial="now",
        widget=forms.RadioSelect,
    )
    finished_at = forms.DateTimeField(
        label="Actual finish date and time",
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local"},
        ),
        help_text=(
            "Only needed when choosing an earlier finish time. "
            "Times are in Israel time."
        ),
    )

    def __init__(self, *args, session, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session

        if not self.is_bound:
            self.initial["finished_at"] = (
                timezone.localtime().replace(
                    second=0,
                    microsecond=0,
                )
            )

    def clean(self):
        cleaned_data = super().clean()
        mode = cleaned_data.get("finish_mode")

        if mode == "now":
            finished_at = timezone.now()
        elif mode == "custom":
            finished_at = cleaned_data.get("finished_at")

            if finished_at is None:
                if "finished_at" not in self.errors:
                    self.add_error(
                        "finished_at",
                        "Enter the actual finish date and time.",
                    )
                return cleaned_data
        else:
            return cleaned_data

        if self.session.started_at is None:
            raise forms.ValidationError(
                "This session has no recorded start time."
            )

        if finished_at < self.session.started_at:
            self.add_error(
                "finished_at",
                "Finish time cannot be before the session started.",
            )
        elif finished_at > timezone.now():
            self.add_error(
                "finished_at",
                "Finish time cannot be in the future.",
            )

        cleaned_data["finished_at"] = finished_at
        return cleaned_data