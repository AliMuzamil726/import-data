"""Dashboard, notification centre and error pages."""
import json

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import module_required

from .models import Notification
from .services import dashboard_metrics


@login_required
@module_required("dashboard")
def dashboard(request):
    search = request.GET.get("q", "").strip()
    metrics = dashboard_metrics(request.user, search=search)

    # Paginate all farmers, 12 per page.
    paginator = Paginator(metrics["farmers_qs"], 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "active_module": "dashboard",
        "cards": metrics["cards"],
        "cards_json": json.dumps(
            [{"key": c["key"], "series": c["series"], "change": c["change"]}
             for c in metrics["cards"]]
        ),
        "recent_farmers": page_obj,       # iterable of farmers for this page
        "page_obj": page_obj,             # for pagination controls
        "is_paginated": page_obj.has_other_pages(),
        "search": metrics.get("search", ""),
    }
    return render(request, "core/dashboard.html", context)


@login_required
def notification_list(request):
    notifications = Notification.objects.for_user(request.user)[:100]
    return render(
        request, "core/notifications.html",
        {"notifications": notifications, "active_module": "notifications"},
    )


@login_required
def notification_feed(request):
    """Polling fallback for browsers where the WebSocket cannot connect."""
    items = Notification.objects.for_user(request.user).filter(is_read=False)[:20]
    return JsonResponse({
        "unread": items.count(),
        "results": [n.as_payload() for n in items],
    })


@login_required
@require_POST
def notification_mark_read(request):
    ids = request.POST.getlist("ids")
    queryset = Notification.objects.for_user(request.user).filter(is_read=False)
    if ids:
        queryset = queryset.filter(id__in=ids)
    updated = queryset.update(is_read=True)
    return JsonResponse({"updated": updated})


def error_403(request, exception=None):
    return render(request, "core/403.html", {"reason": str(exception or "")}, status=403)


def error_404(request, exception=None):
    return render(request, "core/404.html", status=404)


def error_500(request):
    return render(request, "core/500.html", status=500)
