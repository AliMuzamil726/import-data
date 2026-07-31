from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "status", "location", "lead", "start_date", "end_date")
    list_filter = ("status",)
    search_fields = ("name", "code", "location")
    date_hierarchy = "start_date"
