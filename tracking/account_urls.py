from django.urls import path

from .views.accounts import (
    AccountLoginView,
    AccountLogoutView,
    AccountPasswordChangeView,
    ProfileUpdateView,
)


urlpatterns = [
    path(
        "login/",
        AccountLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        AccountLogoutView.as_view(),
        name="logout",
    ),
    path(
        "profile/",
        ProfileUpdateView.as_view(),
        name="profile",
    ),
    path(
        "password/change/",
        AccountPasswordChangeView.as_view(),
        name="password-change",
    ),
]