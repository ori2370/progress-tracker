from django.urls import path

from .views.sessions import (
    GymWorkoutFinishView,
    GymWorkoutTimesUpdateView,
    TennisSessionFinishView,
    TennisSessionTimesUpdateView,
)


urlpatterns = [
    path(
        "gym/workouts/<int:pk>/finish/",
        GymWorkoutFinishView.as_view(),
        name="gym-workout-finish",
    ),
    path(
        "gym/workouts/<int:pk>/times/",
        GymWorkoutTimesUpdateView.as_view(),
        name="gym-workout-times",
    ),
    path(
        "tennis/<int:pk>/finish/",
        TennisSessionFinishView.as_view(),
        name="tennis-finish",
    ),
    path(
        "tennis/<int:pk>/times/",
        TennisSessionTimesUpdateView.as_view(),
        name="tennis-times",
    ),
]