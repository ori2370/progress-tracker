from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from tracking.models import CatalogExercise


class ExerciseCatalogListView(LoginRequiredMixin, ListView):
    login_url = "/account/login/"
    model = CatalogExercise
    template_name = "tracking/exercise_catalog_list.html"
    context_object_name = "exercises"
    paginate_by = 8

    def get_queryset(self):
        queryset = super().get_queryset()

        self.search = self.request.GET.get("q", "").strip()
        self.equipment = self.request.GET.get("equipment", "").strip()

        if self.search:
            queryset = queryset.filter(name__icontains=self.search)

        if self.equipment:
            queryset = queryset.filter(equipment=self.equipment)

        return queryset.order_by("name", "source_id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["search"] = self.search
        context["selected_equipment"] = self.equipment
        context["equipment_options"] = (
            CatalogExercise.objects.exclude(equipment="")
            .order_by("equipment")
            .values_list("equipment", flat=True)
            .distinct()
        )

        parameters = self.request.GET.copy()
        parameters.pop("page", None)
        context["filter_query"] = parameters.urlencode()

        return context