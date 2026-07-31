"""Cached weather observations and forecasts per field."""
from django.db import models


class WeatherData(models.Model):
    """One snapshot for a field: current conditions plus a 7-day forecast."""

    field = models.ForeignKey(
        "fields.Field", on_delete=models.CASCADE, related_name="weather_records"
    )
    fetched_at = models.DateTimeField(auto_now_add=True, db_index=True)
    observed_at = models.DateTimeField(null=True, blank=True)
    temperature_c = models.FloatField(null=True, blank=True)
    feels_like_c = models.FloatField(null=True, blank=True)
    humidity_pct = models.FloatField(null=True, blank=True)
    rain_probability_pct = models.FloatField(null=True, blank=True)
    precipitation_mm = models.FloatField(null=True, blank=True)
    wind_speed_kmh = models.FloatField(null=True, blank=True)
    wind_direction_deg = models.FloatField(null=True, blank=True)
    uv_index = models.FloatField(null=True, blank=True)
    condition_code = models.IntegerField(null=True, blank=True)
    condition_text = models.CharField(max_length=80, blank=True)
    forecast = models.JSONField(
        default=list, blank=True, help_text="List of daily forecast dictionaries."
    )
    source = models.CharField(max_length=40, default="open-meteo")

    class Meta:
        ordering = ("-fetched_at",)
        indexes = [models.Index(fields=["field", "-fetched_at"])]
        verbose_name = "weather record"
        verbose_name_plural = "weather records"

    def __str__(self) -> str:
        return f"{self.field.code} @ {self.fetched_at:%d %b %Y %H:%M}"
