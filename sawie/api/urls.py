from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("farmers", views.FarmerViewSet, basename="farmer")
router.register("fields", views.FieldViewSet, basename="field")
router.register("crops", views.CropViewSet, basename="crop")
router.register("activities", views.ActivityViewSet, basename="activity")
router.register("ndvi", views.NDVIViewSet, basename="ndvi")
router.register("weather", views.WeatherViewSet, basename="weather")
router.register("notifications", views.NotificationViewSet, basename="notification")
router.register("analytics", views.AnalyticsViewSet, basename="analytics")

app_name = "api"

urlpatterns = [
    path("", include(router.urls)),
    path("auth/", include("rest_framework.urls", namespace="rest_framework")),
]
