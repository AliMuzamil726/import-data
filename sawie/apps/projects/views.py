"""Project CRUD."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView

from apps.accounts.permissions import ModuleRequiredMixin, module_required

from .forms import ProjectForm
from .models import Project, ProjectStatus


class ProjectListView(ModuleRequiredMixin, ListView):
    required_module = "projects"
    model = Project
    template_name = "projects/project_list.html"
    context_object_name = "projects"
    paginate_by = 12

    def get_queryset(self):
        queryset = Project.objects.select_related("lead").all()
        query = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(code__icontains=query)
                | Q(location__icontains=query)
            )
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "active_module": "projects",
            "query": self.request.GET.get("q", ""),
            "status": self.request.GET.get("status", ""),
            "statuses": ProjectStatus.choices,
            "total_count": Project.objects.count(),
        })
        return context


class ProjectDetailView(ModuleRequiredMixin, DetailView):
    required_module = "projects"
    model = Project
    template_name = "projects/project_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_module"] = "projects"
        return context


@login_required
@module_required("projects")
def project_create(request):
    if not request.user.can_edit_records:
        messages.error(request, "Your role is read-only for projects.")
        return redirect("projects:list")
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.created_by = request.user
        project.save()
        messages.success(request, f"Created {project.name}.")
        return redirect(project.get_absolute_url())
    return render(
        request, "projects/project_form.html",
        {"form": form, "title": "Add project", "active_module": "projects"},
    )


@login_required
@module_required("projects")
def project_update(request, pk: int):
    project = get_object_or_404(Project, pk=pk)
    if not request.user.can_edit_records:
        messages.error(request, "Your role is read-only for projects.")
        return redirect(project.get_absolute_url())
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved {project.name}.")
        return redirect(project.get_absolute_url())
    return render(
        request, "projects/project_form.html",
        {"form": form, "title": f"Edit {project.name}", "object": project,
         "active_module": "projects"},
    )


@login_required
@module_required("projects")
def project_delete(request, pk: int):
    project = get_object_or_404(Project, pk=pk)
    if not request.user.can_delete_records:
        messages.error(request, "Your role cannot delete projects.")
        return redirect(project.get_absolute_url())
    if request.method == "POST":
        name = project.name
        project.delete()
        messages.success(request, f"Deleted {name}.")
        return redirect("projects:list")
    return render(
        request, "projects/project_confirm_delete.html",
        {"object": project, "active_module": "projects"},
    )
