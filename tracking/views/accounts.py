from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
)
from django.urls import reverse_lazy
from django.views.generic import UpdateView
from ..services.measurements import get_measurement_summary
from ..forms.accounts import ProfileForm


class AccountLoginView(LoginView):
    template_name = "tracking/account_form.html"
    next_page = reverse_lazy("tracking:home")
    redirect_authenticated_user = True
    extra_context = {
        "heading": "Log in",
        "submit_label": "Log in",
    }


class AccountLogoutView(LogoutView):
    next_page = reverse_lazy("tracking:login")


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    login_url = reverse_lazy("tracking:login")
    form_class = ProfileForm
    template_name = "tracking/account_form.html"
    success_url = reverse_lazy("tracking:home")
    extra_context = {
        "heading": "My profile",
        "submit_label": "Save profile",
    }

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            get_measurement_summary(self.request.user)
        )
        return context

class AccountPasswordChangeView(
    LoginRequiredMixin,
    PasswordChangeView,
):
    login_url = reverse_lazy("tracking:login")
    template_name = "tracking/account_form.html"
    success_url = reverse_lazy("tracking:profile")
    extra_context = {
        "heading": "Change password",
        "submit_label": "Save password",
    }