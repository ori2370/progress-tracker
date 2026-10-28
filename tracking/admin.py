from django.contrib import admin
from .models import TennisSession


@admin.register(TennisSession)
class TennisSessionAdmin(admin.ModelAdmin):
    list_display = ("date", "session_type", "focus", "user")
    list_filter = ("session_type",)
    search_fields = ("focus", "notes", "coach_feedback")
# Register your models here.
