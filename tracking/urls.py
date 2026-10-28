from django.urls import path

from .views import (
    TennisSessionBulkDeleteView,
    TennisSessionCreateView,
    TennisSessionListView,
)

app_name = "tracking"

urlpatterns = [
    path(
        "tennis/",
        TennisSessionListView.as_view(),
        name="tennis-list",
    ),
    path(
        "tennis/new/",
        TennisSessionCreateView.as_view(),
        name="tennis-create",
    ),
    path(
        "tennis/delete/",
        TennisSessionBulkDeleteView.as_view(),
        name="tennis-delete",
    ),
]