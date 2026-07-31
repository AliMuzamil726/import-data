"""NDVI upload, processing and history."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView

from apps.accounts.permissions import ModuleRequiredMixin, module_required
from apps.core.scoping import scope_fields
from apps.fields.models import Field
from apps.reports.exporters import export_csv, export_pdf, export_xlsx

from .forms import NDVIUploadForm
from .models import NDVIRecord, NDVIStatus
from .tasks import process_ndvi_record

EXPORT_COLUMNS = [
    ("field", "Field"),
    ("captured_on", "Captured"),
    ("source", "Source"),
    ("index_used", "Index"),
    ("mean_index", "Mean"),
    ("healthy_pct", "Healthy %"),
    ("moderate_pct", "Moderate %"),
    ("poor_pct", "Poor %"),
    ("critical_pct", "Critical %"),
    ("health_score", "Score"),
    ("status", "Status"),
]


def scoped_records(user):
    return NDVIRecord.objects.select_related("field", "field__farmer").filter(
        field__in=scope_fields(Field.objects.all(), user)
    )


class NDVIListView(ModuleRequiredMixin, ListView):
    required_module = "ndvi"
    template_name = "ndvi/ndvi_list.html"
    context_object_name = "records"
    paginate_by = 12

    def get_queryset(self):
        queryset = scoped_records(self.request.user)
        field_id = self.request.GET.get("field")
        status = self.request.GET.get("status")
        if field_id:
            queryset = queryset.filter(field_id=field_id)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        records = scoped_records(self.request.user).filter(status=NDVIStatus.DONE)[:12]
        context.update({
            "active_module": "ndvi",
            "form": NDVIUploadForm(),
            "fields": scope_fields(Field.objects.all(), self.request.user),
            "statuses": NDVIStatus.choices,
            "selected_field": self.request.GET.get("field", ""),
            "trend_json": json.dumps([
                {"date": r.captured_on.strftime("%Y-%m-%d"),
                 "value": r.mean_index or 0, "field": r.field.code}
                for r in reversed(records)
            ]),
        })
        return context


class NDVIDetailView(ModuleRequiredMixin, DetailView):
    required_module = "ndvi"
    template_name = "ndvi/ndvi_detail.html"
    context_object_name = "record"

    def get_queryset(self):
        return scoped_records(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self.object
        context.update({
            "active_module": "ndvi",
            "distribution_json": json.dumps([
                {"label": "Healthy", "value": record.healthy_pct, "colour": "#1E5631"},
                {"label": "Moderate", "value": record.moderate_pct, "colour": "#F59E0B"},
                {"label": "Poor", "value": record.poor_pct, "colour": "#EA580C"},
                {"label": "Critical", "value": record.critical_pct, "colour": "#DC2626"},
            ]),
            "geojson": json.dumps(record.field.as_geojson_feature()),
            "history": scoped_records(self.request.user).filter(
                field=record.field, status=NDVIStatus.DONE
            )[:10],
        })
        return context


@login_required
@module_required("ndvi")
def ndvi_upload(request):
    if not request.user.can_edit_records:
        messages.error(request, "Your role cannot upload imagery.")
        return redirect("ndvi:list")

    form = NDVIUploadForm(request.POST or None, request.FILES or None)
    form.fields["field"].queryset = scope_fields(Field.objects.all(), request.user)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.created_by = request.user
        record.save()
        process_ndvi_record.delay(record.pk)
        messages.success(
            request, f"Imagery received for {record.field.code}. Processing has started."
        )
        return redirect(record.get_absolute_url())
    return render(
        request, "ndvi/ndvi_upload.html",
        {"form": form, "active_module": "ndvi", "title": "Upload imagery"},
    )


@login_required
@module_required("ndvi")
def ndvi_reprocess(request, pk: int):
    record = get_object_or_404(scoped_records(request.user), pk=pk)
    if not request.user.can_edit_records:
        messages.error(request, "Your role cannot reprocess imagery.")
    else:
        process_ndvi_record.delay(record.pk)
        messages.success(request, "Reprocessing started.")
    return redirect(record.get_absolute_url())


@login_required
@module_required("ndvi")
def ndvi_delete(request, pk: int):
    record = get_object_or_404(scoped_records(request.user), pk=pk)
    if not request.user.can_delete_records:
        messages.error(request, "Your role cannot delete imagery.")
        return redirect(record.get_absolute_url())
    if request.method == "POST":
        record.delete()
        messages.success(request, "Scene deleted.")
        return redirect("ndvi:list")
    return render(
        request, "ndvi/ndvi_confirm_delete.html",
        {"object": record, "active_module": "ndvi"},
    )


@login_required
@module_required("ndvi")
def ndvi_export(request, fmt: str):
    rows = scoped_records(request.user)
    exporters = {"csv": export_csv, "xlsx": export_xlsx, "pdf": export_pdf}
    exporter = exporters.get(fmt, export_csv)
    return exporter(
        request, rows, EXPORT_COLUMNS, title="NDVI report", kind="ndvi",
        filename="sawie-ndvi",
    )
