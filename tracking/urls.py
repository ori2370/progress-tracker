from django.urls import path

from .focus_views import (
    TennisFocusCreateView,
    TennisFocusListView,
    TennisFocusUpdateView,
)
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
    path(
        "tennis/focus/",
        TennisFocusListView.as_view(),
        name="tennis-focus-list",
    ),
    path(
        "tennis/focus/new/",
        TennisFocusCreateView.as_view(),
        name="tennis-focus-create",
    ),
    path(
        "tennis/focus/<int:pk>/edit/",
        TennisFocusUpdateView.as_view(),
        name="tennis-focus-update",
    ),
]