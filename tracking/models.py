from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from decimal import Decimal

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
class ExerciseDefinition(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exercise_definitions",
    )
    name = models.CharField(max_length=150)
    equipment = models.CharField(
        max_length=150,
        blank=True,
        help_text="Identify the machine or equipment when relevant.",
    )
    notes = models.TextField(blank=True)
    goal_weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    goal_reps = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ["name", "equipment", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name", "equipment"],
                name="unique_user_exercise_equipment",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(goal_weight_kg__isnull=True)
                    | models.Q(goal_weight_kg__gte=0)
                ),
                name="exercise_goal_nonnegative_weight",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(goal_reps__isnull=True)
                    | models.Q(goal_reps__gte=1)
                ),
                name="exercise_goal_positive_reps",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        goal_weight_kg__isnull=True,
                        goal_reps__isnull=True,
                    )
                    | models.Q(
                        goal_weight_kg__isnull=False,
                        goal_reps__isnull=False,
                    )
                ),
                name="exercise_goal_requires_weight_and_reps",
            ),
        ]

    def clean(self):
        super().clean()

        if (self.goal_weight_kg is None) != (self.goal_reps is None):
            raise ValidationError(
                "For a goal, enter both weight and reps, or leave both blank."
            )

    def __str__(self):
        if self.equipment:
            return f"{self.name} — {self.equipment}"
        return self.name

class GymWorkout(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gym_workouts",
    )
    source_template = models.ForeignKey(
        "WorkoutTemplate",
        on_delete=models.SET_NULL,
        related_name="logged_workouts",
        blank=True,
        null=True,
    )
    date = models.DateField()
    start_time = models.TimeField(blank=True, null=True)
    title = models.CharField(max_length=150)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-start_time", "-created_at"]

    def __str__(self):
        return f"{self.title} — {self.date}"


class GymExercise(models.Model):
    workout = models.ForeignKey(
        GymWorkout,
        on_delete=models.CASCADE,
        related_name="exercises",
    )
    definition = models.ForeignKey(
        ExerciseDefinition,
        on_delete=models.PROTECT,
        related_name="workout_entries",
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=150)
    position = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ["position", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["workout", "position"],
                name="unique_gym_exercise_position",
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=1),
                name="gym_exercise_positive_position",
            ),
        ]

    def clean(self):
        super().clean()

        if self.definition_id and self.workout_id:
            if self.definition.user_id != self.workout.user_id:
                raise ValidationError({
                    "definition": "Choose an exercise from your own library."
                })

    def __str__(self):
        return self.name


class GymSet(models.Model):
    exercise = models.ForeignKey(
        GymExercise,
        on_delete=models.CASCADE,
        related_name="sets",
    )
    number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )
    reps = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )
    weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="External weight in kg. Use 0 for bodyweight only.",
    )

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(
                fields=["exercise", "number"],
                name="unique_gym_set_number",
            ),
            models.CheckConstraint(
                condition=models.Q(number__gte=1),
                name="gym_set_positive_number",
            ),
            models.CheckConstraint(
                condition=models.Q(reps__gte=1),
                name="gym_set_positive_reps",
            ),
            models.CheckConstraint(
                condition=models.Q(weight_kg__gte=0),
                name="gym_set_nonnegative_weight",
            ),
        ]

    def __str__(self):
        return f"Set {self.number}: {self.reps} reps × {self.weight_kg} kg"


class BodyMeasurement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="body_measurements",
    )
    date = models.DateField()
    weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    waist_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(weight_kg__isnull=False)
                    | models.Q(waist_cm__isnull=False)
                ),
                name="body_measurement_requires_value",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(weight_kg__isnull=True)
                    | models.Q(weight_kg__gt=0)
                ),
                name="body_measurement_positive_weight",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(waist_cm__isnull=True)
                    | models.Q(waist_cm__gt=0)
                ),
                name="body_measurement_positive_waist",
            ),
        ]

    def clean(self):
        super().clean()

        if self.weight_kg is None and self.waist_cm is None:
            raise ValidationError(
                "Enter bodyweight, waist measurement, or both."
            )

    def __str__(self):
        return f"Body measurements — {self.date}"

class WorkoutRoutine(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workout_routines",
    )
    name = models.CharField(max_length=150)
    sessions_per_week = models.PositiveSmallIntegerField(
        default=3,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(7),
        ],
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(sessions_per_week__range=(1, 7)),
                name="routine_sessions_between_one_and_seven",
            ),
        ]

    def __str__(self):
        return self.name


class WorkoutTemplate(models.Model):
    routine = models.ForeignKey(
        WorkoutRoutine,
        on_delete=models.CASCADE,
        related_name="templates",
    )
    name = models.CharField(
        max_length=150,
        help_text="For example: FBW A or FBW B.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["routine", "name"],
                name="unique_workout_template_in_routine",
            ),
        ]

    def __str__(self):
        return self.name


class TemplateExercise(models.Model):
    template = models.ForeignKey(
        WorkoutTemplate,
        on_delete=models.CASCADE,
        related_name="exercises",
    )
    definition = models.ForeignKey(
        ExerciseDefinition,
        on_delete=models.PROTECT,
        related_name="template_entries",
    )
    position = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )
    planned_sets = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1)],
    )
    target_reps = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ["position", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "position"],
                name="unique_template_exercise_position",
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=1),
                name="template_exercise_positive_position",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_sets__gte=1),
                name="template_exercise_positive_sets",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(target_reps__isnull=True)
                    | models.Q(target_reps__gte=1)
                ),
                name="template_exercise_positive_reps",
            ),
        ]

    def clean(self):
        super().clean()

        if self.definition_id and self.template_id:
            if (
                self.definition.user_id
                != self.template.routine.user_id
            ):
                raise ValidationError({
                    "definition": "Choose an exercise from your own library."
                })

    def __str__(self):
        return f"{self.template}: {self.definition}"