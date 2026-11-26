from django.utils import timezone

from ..models import BodyMeasurement


def get_measurement_summary(user):
    measurements = BodyMeasurement.objects.filter(
        user=user,
        date__lte=timezone.localdate(),
    ).order_by("-date", "-created_at", "-pk")

    return {
        "latest_weight": measurements.filter(
            weight_kg__isnull=False,
        ).first(),
        "latest_waist": measurements.filter(
            waist_cm__isnull=False,
        ).first(),
    }