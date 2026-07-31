"""Field CRUD, the interactive map and the activity log."""
import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from apps.accounts.permissions import ModuleRequiredMixin, module_required
from apps.core.scoping import scope_fields
from apps.crops.models import CropStatus
from apps.reports.exporters import export_csv, export_pdf, export_xlsx

from .forms import ActivityForm, FieldForm
from .models import FarmActivity, Field, FieldStatus, HealthBand, IrrigationType, SoilType

EXPORT_COLUMNS = [
    ("code", "Code"),
    ("name", "Field"),
    ("farmer", "Farmer"),
    ("area_acres", "Area (ac)"),
    ("soil_type", "Soil"),
    ("irrigation_type", "Irrigation"),
    ("status", "Status"),
    ("health", "Health"),
    ("latest_ndvi", "Latest NDVI"),
    ("latitude", "Latitude"),
    ("longitude", "Longitude"),
]


def filtered_fields(request):
    queryset = scope_fields(
        Field.objects.select_related("farmer", "officer").prefetch_related("crops"),
        request.user,
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    health = request.GET.get("health", "").strip()
    crop = request.GET.get("crop", "").strip()
    farmer = request.GET.get("farmer", "").strip()

    if query:
        queryset = queryset.filter(name__icontains=query) | queryset.filter(
            code__icontains=query
        ) | queryset.filter(farmer__full_name__icontains=query)
    if status:
        queryset = queryset.filter(status=status)
    if health:
        queryset = queryset.filter(health=health)
    if crop:
        queryset = queryset.filter(
            crops__name__iexact=crop, crops__status__in=[CropStatus.PLANNED, CropStatus.GROWING]
        )
    if farmer:
        queryset = queryset.filter(farmer_id=farmer)
    return queryset.distinct()


class FieldListView(ModuleRequiredMixin, ListView):
    required_module = "fields"
    model = Field
    template_name = "fields/field_list.html"
    context_object_name = "fields"
    paginate_by = 15

    def get_queryset(self):
        return filtered_fields(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = scope_fields(Field.objects.all(), self.request.user)
        context.update({
            "active_module": "fields",
            "query": self.request.GET.get("q", ""),
            "status": self.request.GET.get("status", ""),
            "health": self.request.GET.get("health", ""),
            "statuses": FieldStatus.choices,
            "healths": HealthBand.choices,
            "total_count": base.count(),
            "total_acres": sum(f.area_acres for f in base),
        })
        return context


class FieldDetailView(ModuleRequiredMixin, DetailView):
    required_module = "fields"
    model = Field
    template_name = "fields/field_detail.html"

    def get_queryset(self):
        return scope_fields(
            Field.objects.select_related("farmer", "officer").prefetch_related(
                "crops", "activities", "ndvi_records", "weather_records"
            ),
            self.request.user,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_module": "fields",
            "geojson": json.dumps(self.object.as_geojson_feature()),
            "activity_form": ActivityForm(field=self.object),
            "activities": self.object.activities.select_related("crop")[:25],
            "ndvi_records": self.object.ndvi_records.all()[:10],
            "latest_weather": self.object.weather_records.first(),
        })
        return context


def _autogenerate_ndvi(field):
    """Create an estimated NDVI record for a field, ignoring any failure.

    Estimated (no satellite) — labelled as such on the record. Never blocks the
    save if something goes wrong.
    """
    try:
        from apps.ndvi.estimator import generate_for_field
        generate_for_field(field)
    except Exception:
        # NDVI is a nice-to-have on save; never break field creation over it.
        pass


@login_required
@module_required("fields")
def field_create(request):
    if not request.user.can_edit_records:
        messages.error(request, "Your role is read-only for field records.")
        return redirect("fields:list")
    form = FieldForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        field = form.save(commit=False)
        field.created_by = request.user
        field.save()
        # Auto-generate an estimated NDVI so the field has data immediately.
        _autogenerate_ndvi(field)
        messages.success(request, f"Mapped {field.name}.")
        return redirect(field.get_absolute_url())
    return render(
        request, "fields/field_form.html",
        {"form": form, "title": "Add field", "active_module": "fields"},
    )


@login_required
@module_required("fields")
def field_update(request, pk: int):
    field = get_object_or_404(scope_fields(Field.objects.all(), request.user), pk=pk)
    if not request.user.can_edit_records:
        messages.error(request, "Your role is read-only for field records.")
        return redirect(field.get_absolute_url())
    form = FieldForm(request.POST or None, instance=field)
    if request.method == "POST" and form.is_valid():
        field = form.save()
        # Refresh the estimated NDVI in case location/soil/irrigation changed.
        _autogenerate_ndvi(field)
        messages.success(request, f"Saved {field.name}.")
        return redirect(field.get_absolute_url())
    return render(
        request, "fields/field_form.html",
        {"form": form, "title": f"Edit {field.name}", "object": field, "active_module": "fields"},
    )


@login_required
@module_required("fields")
def field_delete(request, pk: int):
    field = get_object_or_404(scope_fields(Field.objects.all(), request.user), pk=pk)
    if not request.user.can_delete_records:
        messages.error(request, "Your role cannot delete field records.")
        return redirect(field.get_absolute_url())
    if request.method == "POST":
        name = field.name
        field.delete()
        messages.success(request, f"Deleted {name}.")
        return redirect("fields:list")
    return render(
        request, "fields/field_confirm_delete.html",
        {"object": field, "active_module": "fields"},
    )


@login_required
@module_required("map")
def field_map(request):
    crops = (
        scope_fields(Field.objects.all(), request.user)
        .exclude(crops__isnull=True)
        .values_list("crops__name", flat=True)
        .distinct()
        .order_by("crops__name")
    )
    return render(
        request, "fields/map.html",
        {
            "active_module": "map",
            "healths": HealthBand.choices,
            "statuses": FieldStatus.choices,
            "crop_names": sorted({c for c in crops if c}),
            "soil_types": SoilType.choices,
            "irrigation_types": IrrigationType.choices,
        },
    )


@login_required
@module_required("map")
def field_geojson(request):
    """FeatureCollection consumed by Leaflet, honouring the active filters."""
    features = [f.as_geojson_feature() for f in filtered_fields(request)]
    return JsonResponse({"type": "FeatureCollection", "features": features})


@login_required
@module_required("fields")
@require_POST
def boundary_save(request, pk: int):
    """Save a polygon drawn on the map without a full form round-trip."""
    field = get_object_or_404(scope_fields(Field.objects.all(), request.user), pk=pk)
    if not request.user.can_edit_records:
        return JsonResponse({"error": "Your role is read-only for field records."}, status=403)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Could not read the request body."}, status=400)

    geometry = payload.get("boundary")
    if geometry and geometry.get("type") != "Polygon":
        return JsonResponse({"error": "Boundary must be a GeoJSON Polygon."}, status=400)

    field.boundary = geometry
    try:
        # Quantise through str() so the DecimalField never sees raw float noise.
        if payload.get("area_acres") is not None:
            field.area_acres = Decimal(str(round(float(payload["area_acres"]), 2)))
        if payload.get("latitude") is not None and payload.get("longitude") is not None:
            field.latitude = Decimal(str(round(float(payload["latitude"]), 6)))
            field.longitude = Decimal(str(round(float(payload["longitude"]), 6)))
    except (TypeError, ValueError, InvalidOperation):
        return JsonResponse({"error": "Coordinates or area were not numbers."}, status=400)

    try:
        field.full_clean()
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
    field.save()
    # A freshly drawn boundary/location means the estimate should refresh too.
    _autogenerate_ndvi(field)
    return JsonResponse({"saved": True, "feature": field.as_geojson_feature()})


@login_required
@module_required("fields")
@require_POST
def activity_create(request, pk: int):
    field = get_object_or_404(scope_fields(Field.objects.all(), request.user), pk=pk)
    if not request.user.can_edit_records:
        messages.error(request, "Your role cannot log activities.")
        return redirect(field.get_absolute_url())
    form = ActivityForm(request.POST, field=field)
    if form.is_valid():
        activity = form.save(commit=False)
        activity.field = field
        activity.created_by = request.user
        activity.save()
        messages.success(request, f"Logged {activity.get_kind_display().lower()}.")
    else:
        messages.error(request, "Check the activity form: " + form.errors.as_text())
    return redirect(field.get_absolute_url())


@login_required
@module_required("fields")
def activity_delete(request, pk: int):
    activity = get_object_or_404(FarmActivity, pk=pk)
    field = activity.field
    if not request.user.can_delete_records:
        messages.error(request, "Your role cannot delete activities.")
    elif request.method == "POST":
        activity.delete()
        messages.success(request, "Activity removed.")
    return redirect(field.get_absolute_url())


@login_required
@module_required("fields")
def field_export(request, fmt: str):
    rows = filtered_fields(request).order_by("code")
    exporters = {"csv": export_csv, "xlsx": export_xlsx, "pdf": export_pdf}
    exporter = exporters.get(fmt)
    if exporter is None:
        messages.error(request, "That export format is not supported.")
        return redirect("fields:list")
    return exporter(
        request, rows, EXPORT_COLUMNS, title="Field report", kind="field",
        filename="sawie-fields",
    )
