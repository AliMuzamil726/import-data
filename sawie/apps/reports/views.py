"""Report centre: pick a dataset, a format, and download it."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.permissions import module_required
from apps.core.scoping import scope_crops, scope_farmers, scope_fields
from apps.crops.models import Crop
from apps.farmers.models import Farmer
from apps.fields.models import Field
from apps.ndvi.models import NDVIRecord
from apps.weather.models import WeatherData

from .models import Report

REPORT_CARDS = [
    {
        "kind": "farmer", "title": "Farmer report", "module": "farmers",
        "description": "Registry with landholding, mapped area and status.",
        "url_name": "farmers:export", "icon": "users",
    },
    {
        "kind": "field", "title": "Field report", "module": "fields",
        "description": "Plots with area, soil, irrigation, health band and coordinates.",
        "url_name": "fields:export", "icon": "square-dashed",
    },
    {
        "kind": "crop", "title": "Crop report", "module": "crops",
        "description": "Cycles with yield per acre, production and farm-gate revenue.",
        "url_name": "crops:export", "icon": "sprout",
    },
    {
        "kind": "ndvi", "title": "NDVI report", "module": "ndvi",
        "description": "Processed scenes with class distribution and health score.",
        "url_name": "ndvi:export", "icon": "satellite",
    },
    {
        "kind": "weather", "title": "Weather report", "module": "weather",
        "description": "Cached observations per field, newest first.",
        "url_name": "weather:export", "icon": "cloud-sun",
    },
]


@login_required
@module_required("reports")
def reports_index(request):
    user = request.user
    counts = {
        "farmer": scope_farmers(Farmer.objects.all(), user).count(),
        "field": scope_fields(Field.objects.all(), user).count(),
        "crop": scope_crops(Crop.objects.all(), user).count(),
        "ndvi": NDVIRecord.objects.filter(
            field__in=scope_fields(Field.objects.all(), user)
        ).count(),
        "weather": WeatherData.objects.filter(
            field__in=scope_fields(Field.objects.all(), user)
        ).count(),
    }
    cards = [
        {**card, "count": counts.get(card["kind"], 0)}
        for card in REPORT_CARDS
        if user.can_access(card["module"])
    ]
    return render(
        request, "reports/index.html",
        {
            "active_module": "reports",
            "cards": cards,
            "history": Report.objects.select_related("generated_by")[:20],
        },
    )
