from django.conf import settings
from django.db import models


class TennisSession(models.Model):
    class SessionType(models.TextChoices):
        LESSON = "lesson", "Group lesson"
        PRACTICE = "practice", "Practice"
        MATCH = "match", "Match"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tennis_sessions",
    )
    date = models.DateField()
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.get_session_type_display()} — {self.date}"