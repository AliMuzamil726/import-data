"""Refresh weather for every active field. Run from cron if you are not using Celery beat."""
from django.core.management.base import BaseCommand

from apps.weather.tasks import refresh_all_field_weather


class Command(BaseCommand):
    help = "Fetch current conditions and the 7-day forecast for every active field."

    def handle(self, *args, **options):
        count = refresh_all_field_weather()
        self.stdout.write(self.style.SUCCESS(f"Refreshed weather for {count} fields."))
