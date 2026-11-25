from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Q
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from ..forms.focus import TennisFocusForm
from ..models import TennisFocus


class OwnedTennisFocusMixin(LoginRequiredMixin):
    login_url = "/account/login/"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class TennisFocusListView(OwnedTennisFocusMixin, ListView):
    model = TennisFocus
    template_name = "tracking/tennis_focus_list.html"
    context_object_name = "focuses"

    def get_queryset(self):
        today = timezone.localdate()

        return super().get_queryset().annotate(
            completed_sessions=Count(
                "sessions",
                filter=Q(
                    sessions__user=self.request.user,
                    sessions__date__gte=F("start_date"),
                    sessions__date__lte=F("end_date"),
                ) & Q(sessions__date__lte=today),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()

        for focus in context["focuses"]:
            if today < focus.start_date:
                focus.schedule_status = "Upcoming"
            elif today > focus.end_date:
                focus.schedule_status = "Period ended"
            else:
                focus.schedule_status = "In progress"

            focus.days_remaining = max(
                (focus.end_date - today).days,
                0,
            )

            if focus.target_sessions:
                focus.sessions_remaining = max(
                    focus.target_sessions - focus.completed_sessions,
                    0,
                )
                focus.progress_percent = min(
                    100,
                    focus.completed_sessions * 100 // focus.target_sessions,
                )
                focus.target_reached = (
                    focus.completed_sessions >= focus.target_sessions
                )

        return context


class TennisFocusCreateView(OwnedTennisFocusMixin, CreateView):
    model = TennisFocus
    form_class = TennisFocusForm
    template_name = "tracking/tennis_focus_form.html"
    success_url = reverse_lazy("tracking:tennis-focus-list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class TennisFocusUpdateView(OwnedTennisFocusMixin, UpdateView):
    model = TennisFocus
    form_class = TennisFocusForm
    template_name = "tracking/tennis_focus_form.html"
    success_url = reverse_lazy("tracking:tennis-focus-list")