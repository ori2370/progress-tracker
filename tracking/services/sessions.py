from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ..models import GymWorkout, TennisSession


@transaction.atomic
def finish_session(*, model, session_pk, user, finished_at):
    if model not in (GymWorkout, TennisSession):
        raise ValueError("Unsupported session model.")

    session = get_object_or_404(
        model.objects.select_for_update(),
        pk=session_pk,
        user=user,
    )

    if not session.is_in_progress:
        raise ValidationError(
            "This session is already completed."
        )

    if session.started_at is None:
        raise ValidationError(
            "This session has no recorded start time."
        )

    if timezone.is_naive(finished_at):
        raise ValidationError(
            "Finish time must include a time zone."
        )

    if finished_at < session.started_at:
        raise ValidationError(
            "Finish time cannot be before the session started."
        )

    if finished_at > timezone.now():
        raise ValidationError(
            "Finish time cannot be in the future."
        )

    session.finished_at = finished_at
    session.status = session.Status.COMPLETED
    session.save(update_fields=["finished_at", "status"])

    return session

@transaction.atomic
def update_session_times(
    *,
    model,
    session_pk,
    user,
    started_at,
    finished_at,
):
    if model not in (GymWorkout, TennisSession):
        raise ValueError("Unsupported session model.")

    session = get_object_or_404(
        model.objects.select_for_update(),
        pk=session_pk,
        user=user,
    )

    if session.is_in_progress:
        raise ValidationError(
            "Finish the active session before editing its times."
        )

    if timezone.is_naive(started_at) or timezone.is_naive(finished_at):
        raise ValidationError("Session times must include a time zone.")

    if finished_at <= started_at:
        raise ValidationError("Finish time must be after the start.")

    if finished_at > timezone.now():
        raise ValidationError("Finish time cannot be in the future.")

    local_start = timezone.localtime(started_at)
    session.started_at = started_at
    session.finished_at = finished_at
    session.date = local_start.date()
    session.start_time = local_start.time().replace(tzinfo=None)

    session.save(
        update_fields=[
            "started_at",
            "finished_at",
            "date",
            "start_time",
        ]
    )

    return session