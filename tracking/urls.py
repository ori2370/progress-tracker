from django.urls import path

from .views import TennisSessionCreateView, TennisSessionListView

app_name = "tracking"

urlpatterns = [
    path("tennis/", TennisSessionListView.as_view(), name="tennis-list"),
    path(
        "tennis/new/",
        TennisSessionCreateView.as_view(),
        name="tennis-create",
    ),
]