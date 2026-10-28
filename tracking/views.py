from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import TennisSessionForm
from .models import TennisSession


class TennisSessionListView(LoginRequiredMixin, ListView):
    model = TennisSession
    template_name = "tracking/tennis_session_list.html"
    context_object_name = "sessions"
    login_url = "/admin/login/"

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

class TennisSessionCreateView(LoginRequiredMixin, CreateView):
    model = TennisSession
    form_class = TennisSessionForm
    template_name = "tracking/tennis_session_form.html"
    success_url = reverse_lazy("tracking:tennis-list")
    login_url = "/admin/login/"

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)