"""Analytics dashboard and its JSON feed."""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from apps.accounts.permissions import module_required

from .services import analytics_payload


@login_required
@module_required("analytics")
def analytics_index(request):
    months = min(max(int(request.GET.get("months", 12)), 3), 24)
    payload = analytics_payload(request.user, months=months)
    return render(
        request, "analytics/index.html",
        {
            "active_module": "analytics",
            "months": months,
            "totals": payload["totals"],
            "payload_json": json.dumps(payload),
        },
    )


@login_required
@module_required("analytics")
def analytics_api(request):
    months = min(max(int(request.GET.get("months", 12)), 3), 24)
    return JsonResponse(analytics_payload(request.user, months=months))
