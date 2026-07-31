"""Scheduled weather refresh."""
import logging

from celery import shared_task

from apps.core.models import NotificationLevel
from apps.core.notifications import notify
from apps.fields.models import Field, FieldStatus

from .services import get_weather_for_field

logger = logging.getLogger("sawie.weather")


@shared_task(name="apps.weather.tasks.refresh_all_field_weather")
def refresh_all_field_weather() -> int:
    """Refresh every active field and raise alerts on severe conditions."""
    refreshed = 0
    for field in Field.objects.filter(status=FieldStatus.ACTIVE).select_related("farmer"):
        record = get_weather_for_field(field, force=True)
        if record is None:
            continue
        refreshed += 1
        if (record.rain_probability_pct or 0) >= 80:
            notify(
                f"Heavy rain expected on {field.code}",
                f"{record.rain_probability_pct:.0f}% chance of rain at {field.name}. "
                "Postpone spraying and irrigation.",
                level=NotificationLevel.WARNING, category="weather",
                url=field.get_absolute_url(),
            )
        if (record.temperature_c or 0) >= 42:
            notify(
                f"Extreme heat at {field.code}",
                f"{record.temperature_c:.0f}°C recorded at {field.name}.",
                level=NotificationLevel.CRITICAL, category="weather",
                url=field.get_absolute_url(),
            )
    logger.info("Refreshed weather for %s fields", refreshed)
    return refreshed
