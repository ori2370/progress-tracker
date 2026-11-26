from django import forms

from ..models import TennisSession


class TennisResultForm(forms.ModelForm):
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
    )

    class Meta:
        model = TennisSession
        fields = ["match_result"]
        labels = {"match_result": "Match result"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["match_result"].choices = (
            TennisSession.MatchResult.choices
        )
        self.fields["match_result"].required = True

        if not self.is_bound:
            self.initial["match_result"] = (
                self.instance.match_result
                or TennisSession.MatchResult.UNFINISHED
            )
            self.initial["set_count"] = self.instance.sets.count()