"""Chart datasets. Every series is aggregated from the database."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.core.scoping import scope_crops, scope_farmers, scope_fields
from apps.crops.models import Crop, CropStatus
from apps.farmers.models import Farmer
from apps.fields.models import Field
from apps.weather.models import WeatherData

MONEY = DecimalField(max_digits=18, decimal_places=2)


def _window_start(months: int):
    """First day of the earliest month in the window, as an aware datetime.

    Returning a datetime (not a date) keeps DateTimeField comparisons
    timezone-aware, which Django warns about otherwise.
    """
    first = (timezone.localdate().replace(day=1)
             - timedelta(days=31 * (months - 1))).replace(day=1)
    return first, timezone.make_aware(
        timezone.datetime.combine(first, timezone.datetime.min.time())
    )


def _filter_from(queryset, date_field: str, months: int):
    """Apply the window filter using the right type for the field."""
    first, aware = _window_start(months)
    model_field = queryset.model._meta.get_field(date_field)
    boundary = aware if model_field.get_internal_type() == "DateTimeField" else first
    return queryset.filter(**{f"{date_field}__gte": boundary}), first


def _month_labels(months: int) -> list[str]:
    cursor = (timezone.localdate().replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)
    labels = []
    for _ in range(months):
        labels.append(cursor.strftime("%b %Y"))
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    return labels


def _bucket(queryset, date_field: str, months: int, value=None) -> list[float]:
    scoped, start = _filter_from(queryset, date_field, months)
    aggregate = Sum(value) if value is not None else Count("id")
    rows = (
        scoped.annotate(bucket=TruncMonth(date_field))
        .values("bucket")
        .annotate(total=Coalesce(aggregate, Decimal("0") if value is not None else 0))
        .order_by("bucket")
    )
    lookup = {r["bucket"].strftime("%Y-%m"): float(r["total"] or 0) for r in rows}
    series, cursor = [], start
    for _ in range(months):
        series.append(round(lookup.get(cursor.strftime("%Y-%m"), 0.0), 2))
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    return series


def analytics_payload(user, months: int = 12) -> dict:
    farmers = scope_farmers(Farmer.objects.all(), user)
    fields = scope_fields(Field.objects.all(), user)
    crops = scope_crops(Crop.objects.all(), user)
    harvested = crops.filter(status=CropStatus.HARVESTED).exclude(actual_harvest_date=None)

    labels = _month_labels(months)

    first_month, _ = _window_start(months)
    cumulative, running = [], farmers.filter(registration_date__lt=first_month).count()
    for value in _bucket(farmers, "registration_date", months):
        running += value
        cumulative.append(running)

    crop_distribution = list(
        crops.values("name")
        .annotate(area=Coalesce(Sum("area_acres"), Decimal("0")), cycles=Count("id"))
        .order_by("-area")[:10]
    )

    weather_impact = list(
        WeatherData.objects.filter(field__in=fields)
        .annotate(bucket=TruncMonth("fetched_at"))
        .values("bucket")
        .annotate(
            temp=Avg("temperature_c"),
            rain=Avg("precipitation_mm"),
            humidity=Avg("humidity_pct"),
        )
        .order_by("bucket")[:months]
    )

    return {
        "labels": labels,
        "farmer_growth": {
            "new": _bucket(farmers, "registration_date", months),
            "cumulative": cumulative,
        },
        "crop_distribution": [
            {"name": row["name"], "area": float(row["area"]), "cycles": row["cycles"]}
            for row in crop_distribution
        ],
        "production_trend": _bucket(
            harvested, "actual_harvest_date", months, value="production_tonnes"
        ),
        "revenue_trend": _bucket(
            harvested.annotate(
                revenue_value=F("production_tonnes") * F("price_per_tonne")
            ),
            "actual_harvest_date", months, value="revenue_value",
        ),
        "area_by_soil": [
            {"label": row["soil_type"], "area": float(row["area"])}
            for row in fields.values("soil_type").annotate(
                area=Coalesce(Sum("area_acres"), Decimal("0"))
            ).order_by("-area")
        ],
        "area_by_irrigation": [
            {"label": row["irrigation_type"], "area": float(row["area"])}
            for row in fields.values("irrigation_type").annotate(
                area=Coalesce(Sum("area_acres"), Decimal("0"))
            ).order_by("-area")
        ],
        "health_split": [
            {"label": row["health"], "count": row["count"]}
            for row in fields.values("health").annotate(count=Count("id")).order_by("-count")
        ],
        "yield_by_crop": [
            {
                "name": row["name"],
                "yield_per_acre": round(
                    float(row["production"] or 0) / float(row["area"] or 1), 3
                ),
            }
            for row in harvested.values("name").annotate(
                production=Coalesce(Sum("production_tonnes"), Decimal("0")),
                area=Coalesce(Sum("area_acres"), Decimal("0")),
            ).order_by("-production")[:8]
        ],
        "weather_impact": [
            {
                "month": row["bucket"].strftime("%b %Y"),
                "temp": round(row["temp"] or 0, 1),
                "rain": round(row["rain"] or 0, 2),
                "humidity": round(row["humidity"] or 0, 1),
            }
            for row in weather_impact
        ],
        "totals": {
            "farmers": farmers.count(),
            "fields": fields.count(),
            "acres": float(fields.aggregate(t=Coalesce(Sum("area_acres"), Decimal("0")))["t"]),
            "production": float(
                harvested.aggregate(t=Coalesce(Sum("production_tonnes"), Decimal("0")))["t"]
            ),
            "revenue": float(
                harvested.aggregate(
                    t=Coalesce(
                        Sum(F("production_tonnes") * F("price_per_tonne"), output_field=MONEY),
                        Decimal("0"),
                    )
                )["t"]
            ),
        },
    }
