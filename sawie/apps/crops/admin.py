from django.contrib import admin

from .models import Crop


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ("name", "variety", "field", "season", "planting_date",
                    "production_tonnes", "status")
    list_filter = ("status", "season", "category")
    search_fields = ("name", "variety", "field__code", "field__farmer__full_name")
    date_hierarchy = "planting_date"
