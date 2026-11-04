from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.urls import reverse_lazy
from django.views.generic import CreateView,ListView
from .forms import MatchSetFormSet, TennisSessionForm
from .models import MatchSet, TennisSession
from django.shortcuts import redirect, render
from django.views import View

from .forms import TennisSessionBulkDeleteForm

class TennisSessionListView(LoginRequiredMixin, ListView):
    model = TennisSession
    template_name = "tracking/tennis_session_list.html"
    context_object_name = "sessions"
    login_url = "/admin/login/"

    SORT_OPTIONS = {
        "newest": ["-date", "-start_time", "-created_at"],
        "oldest": ["date", "start_time", "created_at"],
    }

    def get_session_type(self):
        value = self.request.GET.get("session_type", "")

        if value in TennisSession.SessionType.values:
            return value

        return ""

    def get_sort(self):
        value = self.request.GET.get("sort", "newest")

        if value in self.SORT_OPTIONS:
            return value

        return "newest"

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .filter(user=self.request.user)
            .prefetch_related("sets")
        )

        session_type = self.get_session_type()

        if session_type:
            queryset = queryset.filter(session_type=session_type)

        return queryset.order_by(
            *self.SORT_OPTIONS[self.get_sort()]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["session_types"] = TennisSession.SessionType.choices
        context["selected_type"] = self.get_session_type()
        context["selected_sort"] = self.get_sort()
        return context


class TennisSessionCreateView(LoginRequiredMixin, CreateView):
    model = TennisSession
    form_class = TennisSessionForm
    template_name = "tracking/tennis_session_form.html"
    success_url = reverse_lazy("tracking:tennis-list")
    login_url = "/admin/login/"
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs
    def get_set_count(self):
        if self.request.method != "POST":
            return 0

        if self.request.POST.get("session_type") != "match":
            return 0

        try:
            count = int(self.request.POST.get("set_count", 0))
        except (TypeError, ValueError):
            return 0

        return max(0, min(count, 5))

    def get_set_formset(self):
        if not hasattr(self, "_set_formset"):
            data = (
                self.request.POST
                if self.request.method == "POST"
                else None
            )

            self._set_formset = MatchSetFormSet(
                data=data,
                prefix="sets",
                set_count=self.get_set_count(),
            )

        return self._set_formset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["set_formset"] = self.get_set_formset()
        return context

    def form_valid(self, form):
        formset = self.get_set_formset()

        if not formset.is_valid():
            return self.form_invalid(form)

        with transaction.atomic():
            form.instance.user = self.request.user
            response = super().form_valid(form)

            count = form.cleaned_data["set_count"]

            for index, set_form in enumerate(
                formset.forms[:count],
                start=1,
            ):
                MatchSet.objects.create(
                    session=self.object,
                    number=index,
                    **set_form.cleaned_data,
                )

        return response


class TennisSessionBulkDeleteView(LoginRequiredMixin, View):
    login_url = "/admin/login/"
    template_name = "tracking/tennis_session_confirm_delete.html"

    def get(self, request):
        return redirect("tracking:tennis-list")

    def post(self, request):
        form = TennisSessionBulkDeleteForm(
            request.POST,
            user=request.user,
        )

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"form": form},
                status=400,
            )

        sessions = form.cleaned_data["sessions"]

        if request.POST.get("action") == "confirm":
            with transaction.atomic():
                sessions.delete()

            return redirect("tracking:tennis-list")

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "sessions": sessions,
            },
        )