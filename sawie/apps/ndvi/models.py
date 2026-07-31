"""NDVI processing records."""
from django.db import models
from django.urls import reverse

from apps.core.models import TimeStampedModel


class NDVIStatus(models.TextChoices):
    PENDING = "pending", "Queued"
    PROCESSING = "processing", "Processing"
    DONE = "done", "Complete"
    FAILED = "failed", "Failed"


class NDVIRecord(TimeStampedModel):
    """A processed vegetation-index scene for one field."""

    field = models.ForeignKey(
        "fields.Field", on_delete=models.CASCADE, related_name="ndvi_records"
    )
    captured_on = models.DateField(db_index=True)
    source = models.CharField(
        max_length=60, default="Sentinel-2",
        help_text="Satellite or drone the imagery came from.",
    )
    red_band = models.ImageField(
        upload_to="ndvi/red/", blank=True, null=True,
        help_text="Red band raster. Leave empty when uploading a single RGB image.",
    )
    nir_band = models.ImageField(
        upload_to="ndvi/nir/", blank=True, null=True, help_text="Near-infrared band raster."
    )
    rgb_image = models.ImageField(
        upload_to="ndvi/rgb/", blank=True, null=True,
        help_text="Single RGB image. Processed with a visible-band index (VARI).",
    )
    overlay = models.ImageField(upload_to="ndvi/overlay/", blank=True, null=True)
    status = models.CharField(
        max_length=12, choices=NDVIStatus.choices, default=NDVIStatus.PENDING, db_index=True
    )
    index_used = models.CharField(max_length=10, blank=True, default="NDVI")
    mean_index = models.FloatField(null=True, blank=True)
    min_index = models.FloatField(null=True, blank=True)
    max_index = models.FloatField(null=True, blank=True)
    healthy_pct = models.FloatField(default=0)
    moderate_pct = models.FloatField(default=0)
    poor_pct = models.FloatField(default=0)
    critical_pct = models.FloatField(default=0)
    health_score = models.FloatField(
        default=0, help_text="0-100 score derived from the class distribution."
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ("-captured_on", "-created_at")
        indexes = [models.Index(fields=["field", "-captured_on"])]
        verbose_name = "NDVI record"
        verbose_name_plural = "NDVI records"

    def __str__(self) -> str:
        return f"{self.field.code} — {self.captured_on}"

    def get_absolute_url(self) -> str:
        return reverse("ndvi:detail", args=[self.pk])

    @property
    def band_pairs_supplied(self) -> bool:
        return bool(self.red_band and self.nir_band)

    @property
    def distribution_rows(self):
        """(label, percent, colour) rows for the canopy class bars."""
        return [
            ("Healthy", self.healthy_pct, "#4A7129"),
            ("Moderate", self.moderate_pct, "#9DC46A"),
            ("Poor", self.poor_pct, "#E0A93B"),
            ("Critical", self.critical_pct, "#DC2626"),
        ]
