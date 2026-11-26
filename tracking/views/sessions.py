from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView
from ..forms.session_times import SessionTimesForm
from ..services.sessions import update_session_times
from ..forms.session_finish import SessionFinishForm
from ..models import GymWorkout, TennisSession
from ..services.sessions import finish_session


class SessionFinishView(LoginRequiredMixin, FormView):
    login_url = reverse_lazy("tracking:login")
    form_class = SessionFinishForm
    template_name = "tracking/session_finish.html"

    def get_session(self):
        if not hasattr(self, "_session"):
            self._session = get_object_or_404(
                self.model,
                pk=self.kwargs["pk"],
                user=self.request.user,
            )

        return self._session

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["session"] = self.get_session()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["session"] = self.get_session()
        context["return_url"] = self.get_success_url()
        return context

    def form_valid(self, form):
        try:
            finish_session(
                model=self.model,
                session_pk=self.get_session().pk,
                user=self.request.user,
                finished_at=form.cleaned_data["finished_at"],
            )
        except ValidationError as error:
            for message in error.messages:
                form.add_error(None, message)

            return self.form_invalid(form)

        return HttpResponseRedirect(self.get_success_url())


class GymWorkoutFinishView(SessionFinishView):
    model = GymWorkout

    def get_success_url(self):
        return reverse(
            "tracking:gym-workout-detail",
            kwargs={"pk": self.get_session().pk},
        )


class TennisSessionFinishView(SessionFinishView):
    model = TennisSession

    def get_success_url(self):
        return reverse("tracking:tennis-list")


class SessionTimesUpdateView(SessionFinishView):
    form_class = SessionTimesForm
    template_name = "tracking/session_times_form.html"

    def form_valid(self, form):
        try:
            update_session_times(
                model=self.model,
                session_pk=self.get_session().pk,
                user=self.request.user,
                started_at=form.cleaned_data["started_at"],
                finished_at=form.cleaned_data["finished_at"],
            )
        except ValidationError as error:
            for message in error.messages:
                form.add_error(None, message)

            return self.form_invalid(form)

        return HttpResponseRedirect(self.get_success_url())


class GymWorkoutTimesUpdateView(SessionTimesUpdateView):
    model = GymWorkout

    def get_success_url(self):
        return reverse(
            "tracking:gym-workout-detail",
            kwargs={"pk": self.get_session().pk},
        )


class TennisSessionTimesUpdateView(SessionTimesUpdateView):
    model = TennisSession

    def get_success_url(self):
        return reverse("tracking:tennis-list")