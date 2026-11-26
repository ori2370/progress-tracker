from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from ..forms.tennis import MatchSetFormSet
from ..forms.tennis_result import TennisResultForm
from ..models import MatchSet, TennisSession


class TennisResultUpdateView(LoginRequiredMixin, UpdateView):
    login_url = reverse_lazy("tracking:login")
    model = TennisSession
    form_class = TennisResultForm
    template_name = "tracking/tennis_result_form.html"
    success_url = reverse_lazy("tracking:tennis-list")

    def get_queryset(self):
        return TennisSession.objects.filter(
            user=self.request.user,
            session_type=TennisSession.SessionType.MATCH,
            status=TennisSession.Status.COMPLETED,
        )

    def get_set_count(self):
        if self.request.method != "POST":
            return self.object.sets.count()

        try:
            count = int(self.request.POST.get("set_count", 0))
        except (TypeError, ValueError):
            return 0

        return max(0, min(count, 5))

    def get_set_formset(self):
        if not hasattr(self, "_set_formset"):
            initial = list(
                self.object.sets.order_by("number").values(
                    "my_games",
                    "opponent_games",
                    "my_tiebreak_points",
                    "opponent_tiebreak_points",
                )
            )
            if self.request.method == "POST":
                initial = initial[:self.get_set_count()]
            self._set_formset = MatchSetFormSet(
                data=(
                    self.request.POST
                    if self.request.method == "POST"
                    else None
                ),
                initial=initial,
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
            session = get_object_or_404(
                self.get_queryset().select_for_update(),
                pk=self.object.pk,
            )

            session.match_result = form.cleaned_data["match_result"]
            session.score = ""
            session.save(update_fields=["match_result", "score"])

            session.sets.all().delete()

            count = form.cleaned_data["set_count"]

            for number, set_form in enumerate(
                formset.forms[:count],
                start=1,
            ):
                MatchSet.objects.create(
                    session=session,
                    number=number,
                    **set_form.cleaned_data,
                )

        return HttpResponseRedirect(self.get_success_url())