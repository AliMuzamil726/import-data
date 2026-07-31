"""Celery application."""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("sawie")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "refresh-weather-every-3-hours": {
        "task": "apps.weather.tasks.refresh_all_field_weather",
        "schedule": crontab(minute=0, hour="*/3"),
    },
    "evaluate-ndvi-alerts-daily": {
        "task": "apps.ndvi.tasks.evaluate_ndvi_alerts",
        "schedule": crontab(minute=30, hour=6),
    },
}
