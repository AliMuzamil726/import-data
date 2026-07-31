"""Weather dashboard, tied to the coordinates of each field."""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.accounts.permissions import module_required
from apps.core.scoping import scope_fields
from apps.fields.models import Field
from apps.reports.exporters import export_csv, export_pdf, export_xlsx

from .models import WeatherData
from .services import advisory_for, get_weather_for_field

EXPORT_COLUMNS = [
    ("field", "Field"),
    ("fetched_at", "Fetched"),
    ("temperature_c", "Temp (°C)"),
    ("humidity_pct", "Humidity (%)"),
    ("rain_probability_pct", "Rain chance (%)"),
    ("precipitation_mm", "Rain (mm)"),
    ("wind_speed_kmh", "Wind (km/h)"),
    ("uv_index", "UV"),
    ("condition_text", "Condition"),
]


@login_required
@module_required("weather")
def weather_index(request):
    fields = scope_fields(Field.objects.select_related("farmer"), request.user).order_by("name")
    field_id = request.GET.get("field")
    field = None
    if field_id:
        field = get_object_or_404(fields, pk=field_id)
    elif fields.exists():
        field = fields.first()

    record = get_weather_for_field(field, force=request.GET.get("refresh") == "1") if field else None
    return render(
        request, "weather/index.html",
        {
            "active_module": "weather",
            "fields": fields,
            "field": field,
            "record": record,
            "forecast": record.forecast if record else [],
            "forecast_json": json.dumps(record.forecast if record else []),
            "advisories": advisory_for(record),
        },
    )


@login_required
@module_required("weather")
def weather_api(request, pk: int):
    field = get_object_or_404(scope_fields(Field.objects.all(), request.user), pk=pk)
    record = get_weather_for_field(field, force=request.GET.get("refresh") == "1")
    if record is None:
        return JsonResponse({"error": "The weather provider could not be reached."}, status=502)
    return JsonResponse({
        "field": field.code,
        "temperature_c": record.temperature_c,
        "humidity_pct": record.humidity_pct,
        "rain_probability_pct": record.rain_probability_pct,
        "wind_speed_kmh": record.wind_speed_kmh,
        "uv_index": record.uv_index,
        "condition": record.condition_text,
        "forecast": record.forecast,
        "fetched_at": record.fetched_at.isoformat(),
    })


@login_required
@module_required("weather")
def weather_export(request, fmt: str):
    rows = WeatherData.objects.select_related("field").filter(
        field__in=scope_fields(Field.objects.all(), request.user)
    )[:500]
    exporters = {"csv": export_csv, "xlsx": export_xlsx, "pdf": export_pdf}
    exporter = exporters.get(fmt, export_csv)
    return exporter(
        request, rows, EXPORT_COLUMNS, title="Weather report", kind="weather",
        filename="sawie-weather",
    )
