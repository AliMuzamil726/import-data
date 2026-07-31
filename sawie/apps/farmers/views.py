"""Farmer CRUD, search, filtering and exports."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView

from apps.accounts.permissions import (
    DeleteAccessMixin, ModuleRequiredMixin, WriteAccessMixin, module_required,
)
from apps.core.scoping import scope_farmers
from apps.reports.exporters import export_csv, export_pdf, export_xlsx

from .forms import FarmerForm
from .models import Farmer, FarmerStatus

EXPORT_COLUMNS = [
    ("full_name", "Full name"),
    ("father_name", "Father name"),
    ("cnic", "CNIC"),
    ("phone", "Phone"),
    ("city", "City"),
    ("district", "District"),
    ("total_land_acres", "Declared land (ac)"),
    ("field_count", "Fields"),
    ("mapped_acres", "Mapped (ac)"),
    ("status", "Status"),
    ("registration_date", "Registered"),
]


def filtered_farmers(request):
    queryset = scope_farmers(Farmer.objects.all(), request.user).annotate(
        field_count=Count("fields", distinct=True),
        mapped_acres=Sum("fields__area_acres"),
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    city = request.GET.get("city", "").strip()

    if query:
        queryset = queryset.filter(
            Q(full_name__icontains=query)
            | Q(cnic__icontains=query)
            | Q(phone__icontains=query)
            | Q(village__icontains=query)
            | Q(email__icontains=query)
        )
    if status:
        queryset = queryset.filter(status=status)
    if city:
        queryset = queryset.filter(city__iexact=city)
    return queryset


class FarmerListView(ModuleRequiredMixin, ListView):
    required_module = "farmers"
    model = Farmer
    template_name = "farmers/farmer_list.html"
    context_object_name = "farmers"
    paginate_by = 15

    SORTABLE = {
        "full_name", "-full_name", "registration_date", "-registration_date",
        "total_land_acres", "-total_land_acres", "city", "-city",
    }

    def get_queryset(self):
        sort = self.request.GET.get("sort", "full_name")
        if sort not in self.SORTABLE:
            sort = "full_name"
        return filtered_farmers(self.request).order_by(sort)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base = scope_farmers(Farmer.objects.all(), self.request.user)
        context.update({
            "active_module": "farmers",
            "query": self.request.GET.get("q", ""),
            "status": self.request.GET.get("status", ""),
            "city": self.request.GET.get("city", ""),
            "sort": self.request.GET.get("sort", "full_name"),
            "statuses": FarmerStatus.choices,
            "cities": base.exclude(city="").values_list("city", flat=True).distinct().order_by("city"),
            "total_count": base.count(),
        })
        return context


class FarmerDetailView(ModuleRequiredMixin, DetailView):
    required_module = "farmers"
    model = Farmer
    template_name = "farmers/farmer_detail.html"

    def get_queryset(self):
        return scope_farmers(
            Farmer.objects.select_related("created_by").prefetch_related(
                "fields__crops", "fields__ndvi_records"
            ),
            self.request.user,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fields = self.object.fields.select_related("officer").all()
        crops = [crop for field in fields for crop in field.crops.all()]
        # Average estimated/real NDVI across this farmer's assessed fields.
        ndvi_values = [f.latest_ndvi for f in fields if f.latest_ndvi is not None]
        context.update({
            "active_module": "farmers",
            "fields": fields,
            "crops": crops,
            "mapped_acres": sum(f.area_acres for f in fields),
            "avg_ndvi": round(sum(ndvi_values) / len(ndvi_values), 2) if ndvi_values else None,
        })
        return context


@login_required
@module_required("farmers")
def farmer_create(request):
    if not request.user.can_edit_records:
        messages.error(request, "Your role is read-only for farmer records.")
        return redirect("farmers:list")
    form = FarmerForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        farmer = form.save(commit=False)
        farmer.created_by = request.user
        farmer.save()
        messages.success(request, f"Added {farmer.full_name}.")
        return redirect(farmer.get_absolute_url())
    return render(
        request, "farmers/farmer_form.html",
        {"form": form, "title": "Add farmer", "active_module": "farmers"},
    )


@login_required
@module_required("farmers")
def farmer_update(request, pk: int):
    farmer = get_object_or_404(scope_farmers(Farmer.objects.all(), request.user), pk=pk)
    if not request.user.can_edit_records:
        messages.error(request, "Your role is read-only for farmer records.")
        return redirect(farmer.get_absolute_url())
    form = FarmerForm(request.POST or None, request.FILES or None, instance=farmer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved {farmer.full_name}.")
        return redirect(farmer.get_absolute_url())
    return render(
        request, "farmers/farmer_form.html",
        {"form": form, "title": f"Edit {farmer.full_name}", "object": farmer,
         "active_module": "farmers"},
    )


@login_required
@module_required("farmers")
def farmer_delete(request, pk: int):
    farmer = get_object_or_404(scope_farmers(Farmer.objects.all(), request.user), pk=pk)
    if not request.user.can_delete_records:
        messages.error(request, "Your role cannot delete farmer records.")
        return redirect(farmer.get_absolute_url())
    if request.method == "POST":
        name = farmer.full_name
        farmer.delete()
        messages.success(request, f"Deleted {name} and their fields.")
        return redirect("farmers:list")
    return render(
        request, "farmers/farmer_confirm_delete.html",
        {"object": farmer, "active_module": "farmers"},
    )


@login_required
@module_required("farmers")
def farmer_export(request, fmt: str):
    rows = filtered_farmers(request).order_by("full_name")
    exporters = {"csv": export_csv, "xlsx": export_xlsx, "pdf": export_pdf}
    exporter = exporters.get(fmt)
    if exporter is None:
        messages.error(request, "That export format is not supported.")
        return redirect("farmers:list")
    return exporter(
        request, rows, EXPORT_COLUMNS, title="Farmer report", kind="farmer",
        filename="sawie-farmers",
    )
