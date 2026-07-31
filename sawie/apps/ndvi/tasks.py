"""NDVI processing and alerting."""
import logging

from celery import shared_task
from django.utils import timezone

from apps.core.models import NotificationLevel
from apps.core.notifications import notify
from apps.fields.models import Field

from .models import NDVIRecord, NDVIStatus
from .processing import compute_index

logger = logging.getLogger("sawie.ndvi")


@shared_task(name="apps.ndvi.tasks.process_ndvi_record")
def process_ndvi_record(record_id: int) -> str:
    """Run the index calculation and write the results back to the field."""
    try:
        record = NDVIRecord.objects.select_related("field").get(pk=record_id)
    except NDVIRecord.DoesNotExist:
        logger.error("NDVI record %s vanished before processing", record_id)
        return "missing"

    record.status = NDVIStatus.PROCESSING
    record.save(update_fields=["status"])

    try:
        result = compute_index(record)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user on the record
        record.status = NDVIStatus.FAILED
        record.error_message = str(exc)
        record.save(update_fields=["status", "error_message"])
        logger.warning("NDVI processing failed for %s: %s", record_id, exc)
        notify(
            "NDVI processing failed",
            f"{record.field.code}: {exc}",
            level=NotificationLevel.WARNING, category="ndvi",
            url=record.get_absolute_url(),
        )
        return "failed"

    record.index_used = result.index_used
    record.mean_index = result.mean
    record.min_index = result.minimum
    record.max_index = result.maximum
    record.healthy_pct = result.healthy_pct
    record.moderate_pct = result.moderate_pct
    record.poor_pct = result.poor_pct
    record.critical_pct = result.critical_pct
    record.health_score = result.health_score
    record.status = NDVIStatus.DONE
    record.error_message = ""
    record.overlay.save(
        f"{record.field.code}-{record.captured_on}-{result.index_used.lower()}.png",
        result.overlay, save=False,
    )
    record.save()

    field = record.field
    field.latest_ndvi = result.mean
    field.health = result.band
    field.ndvi_updated_at = timezone.now()
    field.save(update_fields=["latest_ndvi", "health", "ndvi_updated_at"])

    level = {
        "critical": NotificationLevel.CRITICAL,
        "poor": NotificationLevel.WARNING,
    }.get(result.band, NotificationLevel.SUCCESS)
    notify(
        f"{result.index_used} processed for {field.code}",
        f"Mean {result.mean:.2f} — {result.band} canopy, "
        f"{result.healthy_pct:.0f}% of the scene healthy.",
        level=level, category="ndvi", url=record.get_absolute_url(),
    )
    return "done"


@shared_task(name="apps.ndvi.tasks.evaluate_ndvi_alerts")
def evaluate_ndvi_alerts() -> int:
    """Daily sweep for fields whose canopy has dropped into a poor band."""
    flagged = Field.objects.filter(health__in=["poor", "critical"]).select_related("farmer")
    for field in flagged:
        notify(
            f"{field.get_health_display()} canopy on {field.code}",
            f"{field.farmer.full_name} — latest index {field.latest_ndvi:.2f}."
            if field.latest_ndvi is not None else f"{field.farmer.full_name} — review scouting.",
            level=NotificationLevel.CRITICAL if field.health == "critical"
            else NotificationLevel.WARNING,
            category="ndvi", url=field.get_absolute_url(),
        )
    return flagged.count()
