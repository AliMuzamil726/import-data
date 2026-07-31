"""Crop cycle CRUD and exports."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView

from apps.accounts.permissions import ModuleRequiredMixin, module_required
from apps.core.scoping import scope_crops, scope_fields
from apps.fields.models import Field
from apps.reports.exporters import export_csv, export_pdf, export_xlsx

from .forms import CropForm
from .models import Crop, CropCategory, CropStatus, Season

EXPORT_COLUMNS = [
    ("name", "Crop"),
    ("variety", "Variety"),
    ("category", "Category"),
    ("season", "Season"),
    ("field", "Field"),
    ("planting_date", "Planted"),
    ("expected_harvest_date", "Expected harvest"),
    ("area_acres", "Area (ac)"),
    ("production_tonnes", "Production (t)"),
    ("yield_per_acre", "Yield (t/ac)"),
    ("revenue", "Revenue (PKR)"),
    ("status", "Status"),
]


def filtered_crops(request):
    queryset = scope_crops(
        Crop.objects.select_related("field", "field__farmer"), request.user
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    season = request.GET.get("season", "").strip()
    category = request.GET.get("category", "").strip()

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(variety__icontains=query)
            | Q(field__code__icontains=query)
            | Q(field__farmer__full_name__icontains=query)
        )
    if status:
        queryset = queryset.filter(status=status)
    if season:
        queryset = queryset.filter(season=season)
    if category:
        queryset = queryset.filter(category=category)
    return queryset


class CropListView(ModuleRequiredMixin, ListView):
    required_module = "crops"
    model = Crop
    template_name = "crops/crop_list.html"
    context_object_name = "crops"
    paginate_by = 15

    def get_queryset(self):
        return filtered_crops(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = filtered_crops(self.request)
        context.update({
            "active_module": "crops",
            "query": self.request.GET.get("q", ""),
            "status": self.request.GET.get("status", ""),
            "season": self.request.GET.get("season", ""),
            "category": self.request.GET.get("category", ""),
            "statuses": CropStatus.choices,
            "seasons": Season.choices,
            "categories": CropCategory.choices,
            "total_area": base.aggregate(t=Sum("area_acres"))["t"] or 0,
            "total_production": base.aggregate(t=Sum("production_tonnes"))["t"] or 0,
        })
        return context


class CropDetailView(ModuleRequiredMixin, DetailView):
    required_module = "crops"
    model = Crop
    template_name = "crops/crop_detail.html"

    def get_queryset(self):
        return scope_crops(Crop.objects.select_related("field", "field__farmer"), self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_module"] = "crops"
        context["activities"] = self.object.activities.all()[:20]
        # Latest NDVI (estimated or real) for this crop's field, for the card.
        field = self.object.field
        latest_ndvi = (
            field.ndvi_records.order_by("-captured_on", "-created_at").first()
            if field else None
        )
        context["latest_ndvi"] = latest_ndvi
        context["ndvi_field"] = field
        return context


def _crop_form(request, instance=None):
    form = CropForm(request.POST or None, instance=instance)
    form.fields["field"].queryset = scope_fields(
        Field.objects.select_related("farmer"), request.user
    )
    return form


@login_required
@module_required("crops")
def crop_create(request):
    if not request.user.can_edit_records:
        messages.error(request, "Your role is read-only for crop records.")
        return redirect("crops:list")
    form = _crop_form(request)
    if request.method == "POST" and form.is_valid():
        crop = form.save(commit=False)
        crop.created_by = request.user
        crop.save()
        messages.success(request, f"Added {crop.name} on {crop.field.code}.")
        return redirect(crop.get_absolute_url())
    return render(
        request, "crops/crop_form.html",
        {"form": form, "title": "Add crop cycle", "active_module": "crops"},
    )


@login_required
@module_required("crops")
def crop_update(request, pk: int):
    crop = get_object_or_404(scope_crops(Crop.objects.all(), request.user), pk=pk)
    if not request.user.can_edit_records:
        messages.error(request, "Your role is read-only for crop records.")
        return redirect(crop.get_absolute_url())
    form = _crop_form(request, instance=crop)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved {crop.name}.")
        return redirect(crop.get_absolute_url())
    return render(
        request, "crops/crop_form.html",
        {"form": form, "title": f"Edit {crop.name}", "object": crop, "active_module": "crops"},
    )


@login_required
@module_required("crops")
def crop_delete(request, pk: int):
    crop = get_object_or_404(scope_crops(Crop.objects.all(), request.user), pk=pk)
    if not request.user.can_delete_records:
        messages.error(request, "Your role cannot delete crop records.")
        return redirect(crop.get_absolute_url())
    if request.method == "POST":
        label = str(crop)
        crop.delete()
        messages.success(request, f"Deleted {label}.")
        return redirect("crops:list")
    return render(
        request, "crops/crop_confirm_delete.html",
        {"object": crop, "active_module": "crops"},
    )


@login_required
@module_required("crops")
def crop_export(request, fmt: str):
    rows = filtered_crops(request).order_by("-planting_date")
    exporters = {"csv": export_csv, "xlsx": export_xlsx, "pdf": export_pdf}
    exporter = exporters.get(fmt)
    if exporter is None:
        messages.error(request, "That export format is not supported.")
        return redirect("crops:list")
    return exporter(
        request, rows, EXPORT_COLUMNS, title="Crop report", kind="crop",
        filename="sawie-crops",
    )
