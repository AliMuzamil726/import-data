from django.contrib import admin

from .models import NDVIRecord


@admin.register(NDVIRecord)
class NDVIRecordAdmin(admin.ModelAdmin):
    list_display = ("field", "captured_on", "index_used", "mean_index",
                    "health_score", "status")
    list_filter = ("status", "index_used", "source")
    date_hierarchy = "captured_on"
    search_fields = ("field__code", "field__name")
