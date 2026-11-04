from django import forms
from django.forms import BaseFormSet, formset_factory

from .models import TennisFocus, TennisSession

class TennisSessionForm(forms.ModelForm):
    set_count = forms.TypedChoiceField(
        label="Number of sets to record",
        choices=[
            (0, "No scores"),
            (1, "1 set"),
            (2, "2 sets"),
            (3, "3 sets"),
            (4, "4 sets"),
            (5, "5 sets"),
        ],
        coerce=int,
        initial=0,
        required=False,
        empty_value=0,
    )

    class Meta:
        model = TennisSession
        fields = [
            "date",
            "start_time",
            "session_type",
            "focus",
            "training_focus",
            "notes",
            "coach_feedback",
            "match_result",
            "set_count",
            "next_practice_goal",
        ]
        labels = {
            "focus": "Focus / session title",
            "training_focus": "Training focus (optional)",
            "notes": "Notes / observations",
        }
        help_texts = {
            "training_focus": (
                "Link this session to a training goal. "
                "Only sessions within its date range count toward progress."
            ),
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "time"},
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "coach_feedback": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["training_focus"].queryset = (
            TennisFocus.objects.none()
        )

        if user is not None and user.is_authenticated:
            self.instance.user = user
            self.fields["training_focus"].queryset = (
                TennisFocus.objects.filter(user=user)
            )

    def clean(self):
        cleaned_data = super().clean()
        session_type = cleaned_data.get("session_type")

        if session_type == TennisSession.SessionType.MATCH:
            if not cleaned_data.get("match_result"):
                self.add_error(
                    "match_result",
                    "Choose a result for this match.",
                )
        else:
            cleaned_data["match_result"] = ""
            cleaned_data["set_count"] = 0

        if session_type != TennisSession.SessionType.LESSON:
            cleaned_data["coach_feedback"] = ""

        return cleaned_data


class MatchSetForm(forms.Form):
    my_games = forms.IntegerField(
        label="Your games",
        min_value=0,
    )
    opponent_games = forms.IntegerField(
        label="Opponent’s games",
        min_value=0,
    )
    my_tiebreak_points = forms.IntegerField(
        label="Your tie-break points",
        min_value=0,
        required=False,
    )
    opponent_tiebreak_points = forms.IntegerField(
        label="Opponent’s tie-break points",
        min_value=0,
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()

        my_games = cleaned_data.get("my_games")
        opponent_games = cleaned_data.get("opponent_games")

        if my_games is None or opponent_games is None:
            return cleaned_data

        has_tiebreak = (my_games, opponent_games) in (
            (7, 6),
            (6, 7),
        )

        if has_tiebreak:
            mine = cleaned_data.get("my_tiebreak_points")
            theirs = cleaned_data.get("opponent_tiebreak_points")

            if mine is None or theirs is None:
                raise forms.ValidationError(
                    "Enter both tie-break point totals."
                )
        else:
            cleaned_data["my_tiebreak_points"] = None
            cleaned_data["opponent_tiebreak_points"] = None

        return cleaned_data


class BaseMatchSetFormSet(BaseFormSet):
    def __init__(self, *args, set_count=0, **kwargs):
        self.set_count = set_count
        super().__init__(*args, **kwargs)

        for index, form in enumerate(self.forms):
            if index < self.set_count:
                form.empty_permitted = False

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        if self.total_form_count() != 5:
            raise forms.ValidationError(
                "Invalid score form. Refresh the page and try again."
            )

        for index, form in enumerate(self.forms):
            if index >= self.set_count and form.has_changed():
                raise forms.ValidationError(
                    "Scores were submitted outside the selected set count."
                )


MatchSetFormSet = formset_factory(
    MatchSetForm,
    formset=BaseMatchSetFormSet,
    extra=5,
    max_num=5,
    validate_max=True,
    absolute_max=5,
)

class TennisSessionBulkDeleteForm(forms.Form):
    sessions = forms.ModelMultipleChoiceField(
        queryset=TennisSession.objects.none(),
        required=True,
        error_messages={
            "required": "Select at least one session.",
            "invalid_choice": (
                "Some selected sessions are unavailable. "
                "Return to the list and select them again."
            ),
        },
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sessions"].queryset = (
            TennisSession.objects.filter(user=user)
        )