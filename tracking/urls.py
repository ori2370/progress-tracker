from django.urls import include, path
from .views.home import HomeView
from .views.tennis_result import TennisResultUpdateView
from .views.focus import (
    TennisFocusCreateView,
    TennisFocusListView,
    TennisFocusUpdateView,
)
from .views.tennis import (
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
    path("", include("tracking.session_urls")),
    path("gym/", include("tracking.gym_urls")),
    path("account/", include("tracking.account_urls")),
    path("", HomeView.as_view(), name="home"),
    path(
        "tennis/<int:pk>/result/",
        TennisResultUpdateView.as_view(),
        name="tennis-result-update",
    ),
]