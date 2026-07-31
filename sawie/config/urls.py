"""Root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("farmers/", include("apps.farmers.urls")),
    path("fields/", include("apps.fields.urls")),
    path("crops/", include("apps.crops.urls")),
    path("weather/", include("apps.weather.urls")),
    path("ndvi/", include("apps.ndvi.urls")),
    path("analytics/", include("apps.analytics.urls")),
    path("reports/", include("apps.reports.urls")),
    path("projects/", include("apps.projects.urls")),
    path("api/v1/", include("api.urls")),
]

handler403 = core_views.error_403
handler404 = core_views.error_404
handler500 = core_views.error_500

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
