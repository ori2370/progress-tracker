from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from tracking.models import ExerciseDefinition
from tracking.services.youtube import (
    YouTubeSearchError,
    search_exercise_videos,
)


@method_decorator(never_cache, name="dispatch")
class ExerciseVideoSearchView(LoginRequiredMixin, View):
    login_url = "/account/login/"
    http_method_names = ["get"]

    def get(self, request, pk):
        exercise = get_object_or_404(
            ExerciseDefinition,
            pk=pk,
            user=request.user,
        )

        try:
            videos = search_exercise_videos(exercise.name)
        except YouTubeSearchError as error:
            return JsonResponse(
                {"error": str(error)},
                status=503,
            )

        return JsonResponse({"videos": videos})