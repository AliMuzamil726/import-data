from django.contrib import admin

from .models import Farmer


@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ("sawie_id", "full_name", "cnic", "phone", "city", "total_land_acres",
                    "status", "registration_date")
    list_filter = ("status", "province", "district", "city")
    search_fields = ("full_name", "cnic", "phone", "email", "village")
    date_hierarchy = "registration_date"
    autocomplete_fields = ()
