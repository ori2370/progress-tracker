from django.conf import settings
from django.db import models


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