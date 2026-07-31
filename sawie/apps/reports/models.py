"""Generated report artefacts."""
from django.conf import settings
from django.db import models


class ReportKind(models.TextChoices):
    FARMER = "farmer", "Farmer report"
    FIELD = "field", "Field report"
    CROP = "crop", "Crop report"
    NDVI = "ndvi", "NDVI report"
    WEATHER = "weather", "Weather report"


class ReportFormat(models.TextChoices):
    PDF = "pdf", "PDF"
    XLSX = "xlsx", "Excel"
    CSV = "csv", "CSV"


class Report(models.Model):
    """Audit trail of every export produced by the platform."""

    kind = models.CharField(max_length=12, choices=ReportKind.choices)
    fmt = models.CharField("format", max_length=6, choices=ReportFormat.choices)
    filters = models.JSONField(default=dict, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="reports"
    )
    generated_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-generated_at",)

    def __str__(self) -> str:
        return f"{self.get_kind_display()} ({self.fmt}) — {self.generated_at:%d %b %Y %H:%M}"
