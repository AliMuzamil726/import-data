from django.contrib import admin

from .models import WeatherData


@admin.register(WeatherData)
class WeatherDataAdmin(admin.ModelAdmin):
    list_display = ("field", "fetched_at", "temperature_c", "humidity_pct",
                    "rain_probability_pct", "wind_speed_kmh", "condition_text")
    list_filter = ("source", "condition_text")
    date_hierarchy = "fetched_at"
