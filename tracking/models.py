from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class TennisFocus(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tennis_focuses",
    )
    title = models.CharField(max_length=150)
    goal = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    target_sessions = models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        verbose_name_plural = "tennis focuses"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    end_date__gte=models.F("start_date")
                ),
                name="tennis_focus_valid_date_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(target_sessions__isnull=True)
                    | models.Q(target_sessions__gte=1)
                ),
                name="tennis_focus_positive_session_target",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            raise ValidationError({
                "end_date": "End date must be on or after the start date."
            })

    def __str__(self):
        return self.title


class TennisSession(models.Model):
    class SessionType(models.TextChoices):
        LESSON = "lesson", "Group lesson"
        PRACTICE = "practice", "Practice"
        MATCH = "match", "Match"

    class MatchResult(models.TextChoices):
        WON = "won", "Won"
        LOST = "lost", "Lost"
        UNFINISHED = "unfinished", "Unfinished"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tennis_sessions",
    )
    training_focus = models.ForeignKey(
        TennisFocus,
        on_delete=models.SET_NULL,
        related_name="sessions",
        blank=True,
        null=True,
    )
    date = models.DateField()
    start_time = models.TimeField(blank=True, null=True)
    session_type = models.CharField(
        max_length=10,
        choices=SessionType.choices,
    )
    focus = models.CharField(max_length=150)
    notes = models.TextField(blank=True)
    coach_feedback = models.TextField(blank=True)
    next_practice_goal = models.CharField(
        max_length=250,
        blank=True,
    )
    match_result = models.CharField(
        max_length=10,
        choices=MatchResult.choices,
        blank=True,
    )
    score = models.CharField(
        max_length=100,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-start_time", "-created_at"]

    def clean(self):
        super().clean()

        if self.training_focus_id:
            if self.training_focus.user_id != self.user_id:
                raise ValidationError({
                    "training_focus": "Choose one of your own training focuses."
                })

    def __str__(self):
        return f"{self.get_session_type_display()} — {self.date}"


class MatchSet(models.Model):
    session = models.ForeignKey(
        TennisSession,
        on_delete=models.CASCADE,
        related_name="sets",
    )
    number = models.PositiveSmallIntegerField()
    my_games = models.PositiveSmallIntegerField()
    opponent_games = models.PositiveSmallIntegerField()
    my_tiebreak_points = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
    )
    opponent_tiebreak_points = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "number"],
                name="unique_set_number_per_session",
            ),
            models.CheckConstraint(
                condition=models.Q(number__gte=1),
                name="match_set_number_at_least_one",
            ),
        ]

    def __str__(self):
        return (
            f"Set {self.number}: "
            f"{self.my_games}–{self.opponent_games}"
        )