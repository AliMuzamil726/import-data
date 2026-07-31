from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("kind", "fmt", "row_count", "generated_by", "generated_at")
    list_filter = ("kind", "fmt")
    date_hierarchy = "generated_at"
