"""Generate estimated NDVI for existing fields that don't have coordinates-based data.

Usage:
    python manage.py estimate_ndvi            # all fields with coordinates
    python manage.py estimate_ndvi --missing  # only fields without any NDVI yet
"""
from django.core.management.base import BaseCommand

from apps.fields.models import Field
from apps.ndvi.estimator import generate_for_field


class Command(BaseCommand):
    help = "Generate estimated NDVI records for existing fields."

    def add_arguments(self, parser):
        parser.add_argument(
            "--missing", action="store_true",
            help="Only fields that have no NDVI record yet.",
        )

    def handle(self, *args, **options):
        qs = Field.objects.filter(latitude__isnull=False, longitude__isnull=False)
        if options["missing"]:
            qs = qs.filter(ndvi_records__isnull=True).distinct()

        done = 0
        for field in qs:
            if generate_for_field(field):
                done += 1
        self.stdout.write(self.style.SUCCESS(
            f"Generated estimated NDVI for {done} field(s)."
        ))
