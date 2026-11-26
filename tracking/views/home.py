from datetime import timedelta
from ..services.measurements import get_measurement_summary
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView

from ..models import GymWorkout, TennisSession


class HomeView(LoginRequiredMixin, TemplateView):
    login_url = reverse_lazy("tracking:login")
    template_name = "tracking/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = timezone.localdate()
        month_start = today.replace(day=1)
        next_month = (
            month_start + timedelta(days=32)
        ).replace(day=1)

        filters = {
            "user": self.request.user,
            "status": "completed",
            "date__gte": month_start,
            "date__lt": next_month,
            "date__lte": today,
        }

        gym_count = GymWorkout.objects.filter(**filters).count()
        tennis_count = TennisSession.objects.filter(**filters).count()

        context.update({
            "progress_month": month_start,
            "gym_completed_count": gym_count,
            "tennis_completed_count": tennis_count,
            "total_completed_count": gym_count + tennis_count,
        })
        context.update(
            get_measurement_summary(self.request.user)
        )
        return context