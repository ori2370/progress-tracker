from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache


@method_decorator(never_cache, name="dispatch")
class LivenessView(View):
    def get(self, request):
        return JsonResponse({"status": "alive"})


@method_decorator(never_cache, name="dispatch")
class ReadinessView(View):
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return JsonResponse(
                {"status": "not_ready"},
                status=503,
            )

        return JsonResponse({"status": "ready"})