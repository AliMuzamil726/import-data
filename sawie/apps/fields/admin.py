from django.contrib import admin

from .models import FarmActivity, Field


class ActivityInline(admin.TabularInline):
    model = FarmActivity
    extra = 0


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "farmer", "area_acres", "soil_type",
                    "irrigation_type", "status", "health")
    list_filter = ("status", "health", "soil_type", "irrigation_type")
    search_fields = ("code", "name", "farmer__full_name")
    inlines = [ActivityInline]


@admin.register(FarmActivity)
class FarmActivityAdmin(admin.ModelAdmin):
    list_display = ("field", "kind", "performed_on", "detail", "quantity", "unit", "cost")
    list_filter = ("kind",)
    date_hierarchy = "performed_on"
