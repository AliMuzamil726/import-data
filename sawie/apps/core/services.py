"""Dashboard aggregation. Every number here comes from the database."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from apps.core.scoping import scope_crops, scope_farmers, scope_fields
from apps.crops.models import Crop, CropStatus
from apps.farmers.models import Farmer
from apps.fields.models import Field, HealthBand

MONEY = DecimalField(max_digits=18, decimal_places=2)


def _window_start(months: int):
    """First day of the earliest month in the window, as an aware datetime."""
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


def _pct_change(current: float, previous: float) -> float:
    if not previous:
        return 100.0 if current else 0.0
    return round(((current - previous) / previous) * 100, 1)


def _monthly_series(queryset, date_field: str, months: int = 6, value=None) -> list[float]:
    """Return a `months`-long series ending with the current month."""
    scoped, start = _filter_from(queryset, date_field, months)
    aggregate = Sum(value) if value else Count("id")
    rows = (
        scoped.annotate(bucket=TruncMonth(date_field))
        .values("bucket")
        .annotate(total=Coalesce(aggregate, Decimal("0") if value else 0))
        .order_by("bucket")
    )
    lookup = {row["bucket"].strftime("%Y-%m"): float(row["total"] or 0) for row in rows}

    series, cursor = [], start
    for _ in range(months):
        series.append(lookup.get(cursor.strftime("%Y-%m"), 0.0))
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    return series


def dashboard_metrics(user, search: str = "") -> dict:
    """Headline cards plus the list of recently registered farmers.

    Revenue, Production and Open-alerts cards were removed by request, along
    with the crop-mix / health / harvest panels. The dashboard now shows the
    top summary cards and a live feed of newly added farmers.
    """
    today = timezone.localdate()
    window_start = today - timedelta(days=30)
    prior_start = today - timedelta(days=60)

    farmers = scope_farmers(Farmer.objects.all(), user)
    fields = scope_fields(Field.objects.all(), user)
    crops = scope_crops(Crop.objects.all(), user)

    farmer_now = farmers.filter(registration_date__gte=window_start).count()
    farmer_prev = farmers.filter(
        registration_date__gte=prior_start, registration_date__lt=window_start
    ).count()

    field_now = fields.filter(created_at__date__gte=window_start).count()
    field_prev = fields.filter(
        created_at__date__gte=prior_start, created_at__date__lt=window_start
    ).count()

    total_acres = float(fields.aggregate(t=Coalesce(Sum("area_acres"), Decimal("0")))["t"])
    healthy = fields.filter(health=HealthBand.HEALTHY).count()
    assessed = fields.exclude(health=HealthBand.UNKNOWN).count()

    return {
        "cards": [
            {
                "key": "farmers", "label": "Farmers", "icon": "users",
                "value": farmers.count(), "suffix": "",
                "change": _pct_change(farmer_now, farmer_prev),
                "caption": f"{farmer_now} added in 30 days",
                "series": _monthly_series(farmers, "registration_date"),
            },
            {
                "key": "fields", "label": "Fields", "icon": "square-dashed",
                "value": fields.count(), "suffix": "",
                "change": _pct_change(field_now, field_prev),
                "caption": f"{field_now} mapped in 30 days",
                "series": _monthly_series(fields, "created_at"),
            },
            {
                "key": "crops", "label": "Active crops", "icon": "sprout",
                "value": crops.filter(status=CropStatus.GROWING).count(), "suffix": "",
                "change": _pct_change(
                    crops.filter(planting_date__gte=window_start).count(),
                    crops.filter(planting_date__gte=prior_start,
                                 planting_date__lt=window_start).count(),
                ),
                "caption": f"{crops.count()} cycles on record",
                "series": _monthly_series(crops, "planting_date"),
            },
            {
                "key": "acres", "label": "Total acres", "icon": "ruler",
                "value": round(total_acres, 1), "suffix": " ac",
                "change": _pct_change(field_now, field_prev),
                "caption": f"across {fields.count()} plots",
                "series": _monthly_series(fields, "created_at", value="area_acres"),
            },
            {
                "key": "healthy", "label": "Healthy fields", "icon": "heart-pulse",
                "value": healthy, "suffix": f" / {assessed}" if assessed else "",
                "change": round((healthy / assessed * 100) if assessed else 0, 1),
                "change_is_share": True,
                "caption": "NDVI band = healthy",
                "series": _monthly_series(fields.filter(health=HealthBand.HEALTHY), "created_at"),
            },
        ],
        # Full farmer queryset (paginated by the view), searchable.
        "farmers_qs": _farmers_qs(farmers, search),
        "search": search,
    }


def _farmers_qs(farmers, search: str):
    from django.db.models import Q

    qs = farmers.select_related("created_by").prefetch_related(
        "fields__crops"
    ).annotate(field_count=Count("fields", distinct=True))
    if search:
        qs = qs.filter(
            Q(full_name__icontains=search)
            | Q(sawie_id__icontains=search)
            | Q(cnic__icontains=search)
            | Q(phone__icontains=search)
            | Q(city__icontains=search)
            | Q(village__icontains=search)
        )
    return qs.order_by("-created_at")
