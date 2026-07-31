"""Estimated NDVI generator (no satellite / no external account).

IMPORTANT — this is NOT real NDVI. Real NDVI needs a near-infrared satellite
band. This module produces a *plausible estimate* from the field's own
attributes (soil, irrigation, status, area) plus a small deterministic wobble,
so the platform's NDVI flow works end-to-end without any external service.

Every record it creates is labelled index_used="EST-NDVI" and source
"Estimated (no satellite)" so it can never be mistaken for a real scene, and so
that switching to a real provider (e.g. Sentinel Hub) later is a clean swap.
"""
from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal


# How favourable each soil type is for a healthy canopy (0..1 weight).
SOIL_SCORE = {
    "loam": 0.90,
    "clay_loam": 0.82,
    "sandy_loam": 0.78,
    "silt": 0.80,
    "clay": 0.70,
    "sandy": 0.58,
    "saline": 0.40,
}

# How favourable each irrigation method is (0..1 weight).
IRRIGATION_SCORE = {
    "drip": 0.92,
    "sprinkler": 0.85,
    "canal": 0.80,
    "mixed": 0.82,
    "tubewell": 0.72,
    "rainfed": 0.55,
}

# Field status modifier.
STATUS_SCORE = {
    "active": 1.00,
    "harvested": 0.70,
    "fallow": 0.45,
    "retired": 0.30,
}


def _wobble(seed_text: str) -> float:
    """Deterministic pseudo-random value in [-0.06, +0.06] from a seed string.

    Deterministic so the same field on the same day always gives the same
    estimate (no flicker on page refresh), but different fields differ.
    """
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    # take 4 hex chars -> 0..65535 -> map to -0.06..+0.06
    n = int(digest[:4], 16) / 65535.0
    return (n - 0.5) * 0.12


def estimate_ndvi_value(field) -> float:
    """Return an estimated mean NDVI in a realistic 0.15..0.85 range."""
    soil = SOIL_SCORE.get(getattr(field, "soil_type", ""), 0.70)
    irrig = IRRIGATION_SCORE.get(getattr(field, "irrigation_type", ""), 0.72)
    status = STATUS_SCORE.get(getattr(field, "status", "active"), 1.0)

    # Weighted blend of the drivers, scaled into a sensible canopy range.
    # soil/irrig are ~0.4..0.92; this maps a typical field into ~0.35..0.75.
    base = (soil * 0.40 + irrig * 0.38) * 0.92
    value = base * status

    seed = f"{getattr(field, 'code', '')}-{getattr(field, 'pk', '')}-{date.today().isoformat()}"
    value += _wobble(seed)

    # Clamp to a believable vegetation range.
    return round(max(0.15, min(0.85, value)), 3)


def band_for(value: float) -> str:
    """Map an NDVI value onto the platform's health bands."""
    if value >= 0.50:
        return "healthy"
    if value >= 0.30:
        return "moderate"
    if value >= 0.15:
        return "poor"
    return "critical"


def _distribution(value: float) -> dict:
    """Rough class split around the mean, summing to 100."""
    if value >= 0.60:
        healthy, moderate, poor, critical = 72, 20, 6, 2
    elif value >= 0.50:
        healthy, moderate, poor, critical = 58, 28, 10, 4
    elif value >= 0.40:
        healthy, moderate, poor, critical = 40, 38, 16, 6
    elif value >= 0.30:
        healthy, moderate, poor, critical = 24, 40, 26, 10
    else:
        healthy, moderate, poor, critical = 10, 28, 38, 24
    return {"healthy": healthy, "moderate": moderate, "poor": poor, "critical": critical}


def generate_for_field(field, *, captured_on: date | None = None):
    """Create (or refresh) an estimated NDVIRecord for a field and update it.

    Returns the NDVIRecord, or None if the field has no coordinates yet.
    Safe to call on every save — it replaces the day's estimate rather than
    piling up duplicates.
    """
    from django.utils import timezone

    from .models import NDVIRecord, NDVIStatus

    if field.latitude is None or field.longitude is None:
        return None

    captured_on = captured_on or timezone.localdate()
    value = estimate_ndvi_value(field)
    band = band_for(value)
    dist = _distribution(value)
    score = round(
        dist["healthy"] * 1.0 + dist["moderate"] * 0.7
        + dist["poor"] * 0.35 + dist["critical"] * 0.05,
        1,
    )

    # One estimate per field per day: update today's if it exists.
    record, _ = NDVIRecord.objects.update_or_create(
        field=field,
        captured_on=captured_on,
        source="Estimated (no satellite)",
        defaults={
            "status": NDVIStatus.DONE,
            "index_used": "EST-NDVI",
            "mean_index": value,
            "min_index": round(max(-0.1, value - 0.25), 3),
            "max_index": round(min(1.0, value + 0.20), 3),
            "healthy_pct": dist["healthy"],
            "moderate_pct": dist["moderate"],
            "poor_pct": dist["poor"],
            "critical_pct": dist["critical"],
            "health_score": score,
            "error_message": "",
        },
    )

    # Push the summary onto the field itself.
    field.latest_ndvi = value
    field.health = band
    field.ndvi_updated_at = timezone.now()
    field.save(update_fields=["latest_ndvi", "health", "ndvi_updated_at"])

    return record
