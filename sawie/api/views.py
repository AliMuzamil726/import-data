"""REST viewsets. Every queryset is scoped to the caller's role."""
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.analytics.services import analytics_payload
from apps.core.models import Notification
from apps.core.scoping import scope_crops, scope_farmers, scope_fields
from apps.crops.models import Crop
from apps.farmers.models import Farmer
from apps.fields.models import FarmActivity, Field
from apps.ndvi.models import NDVIRecord
from apps.weather.models import WeatherData
from apps.weather.services import get_weather_for_field

from .serializers import (
    ActivitySerializer, CropSerializer, FarmerSerializer, FieldSerializer,
    NDVISerializer, NotificationSerializer, WeatherSerializer,
)


class ScopedModelViewSet(viewsets.ModelViewSet):
    """Applies role scoping and records the creating user."""

    scope = staticmethod(lambda qs, user: qs)

    def get_queryset(self):
        return type(self).scope(self.queryset, self.request.user)

    def perform_create(self, serializer):
        if hasattr(serializer.Meta.model, "created_by"):
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()


class FarmerViewSet(ScopedModelViewSet):
    queryset = Farmer.objects.all()
    serializer_class = FarmerSerializer
    scope = staticmethod(scope_farmers)
    filterset_fields = ["status", "city", "district", "province"]
    search_fields = ["full_name", "cnic", "phone", "village", "email"]
    ordering_fields = ["full_name", "registration_date", "total_land_acres"]

    @action(detail=True, methods=["get"])
    def fields(self, request, pk=None):
        farmer = self.get_object()
        serializer = FieldSerializer(farmer.fields.all(), many=True)
        return Response(serializer.data)


class FieldViewSet(ScopedModelViewSet):
    queryset = Field.objects.select_related("farmer").all()
    serializer_class = FieldSerializer
    scope = staticmethod(scope_fields)
    filterset_fields = ["status", "health", "soil_type", "irrigation_type", "farmer"]
    search_fields = ["code", "name", "farmer__full_name"]
    ordering_fields = ["code", "area_acres", "created_at"]

    @action(detail=False, methods=["get"])
    def geojson(self, request):
        features = [f.as_geojson_feature() for f in self.get_queryset()]
        return Response({"type": "FeatureCollection", "features": features})

    @action(detail=True, methods=["get"])
    def weather(self, request, pk=None):
        record = get_weather_for_field(self.get_object())
        if record is None:
            return Response({"detail": "Weather provider unavailable."}, status=502)
        return Response(WeatherSerializer(record).data)


class CropViewSet(ScopedModelViewSet):
    queryset = Crop.objects.select_related("field").all()
    serializer_class = CropSerializer
    scope = staticmethod(scope_crops)
    filterset_fields = ["status", "season", "category", "field"]
    search_fields = ["name", "variety", "field__code"]
    ordering_fields = ["planting_date", "production_tonnes", "area_acres"]


class ActivityViewSet(ScopedModelViewSet):
    queryset = FarmActivity.objects.select_related("field").all()
    serializer_class = ActivitySerializer
    filterset_fields = ["kind", "field", "crop"]
    ordering_fields = ["performed_on"]

    def get_queryset(self):
        return self.queryset.filter(
            field__in=scope_fields(Field.objects.all(), self.request.user)
        )


class NDVIViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NDVIRecord.objects.select_related("field").all()
    serializer_class = NDVISerializer
    filterset_fields = ["status", "field", "index_used"]
    ordering_fields = ["captured_on", "mean_index"]

    def get_queryset(self):
        return self.queryset.filter(
            field__in=scope_fields(Field.objects.all(), self.request.user)
        )


class WeatherViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WeatherData.objects.select_related("field").all()
    serializer_class = WeatherSerializer
    filterset_fields = ["field"]
    ordering_fields = ["fetched_at"]

    def get_queryset(self):
        return self.queryset.filter(
            field__in=scope_fields(Field.objects.all(), self.request.user)
        )


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    filterset_fields = ["level", "category", "is_read"]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return self.queryset.for_user(self.request.user)

    @action(detail=False, methods=["patch"])
    def read_all(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"updated": updated})


class AnalyticsViewSet(viewsets.ViewSet):
    """Read-only analytics feed for external dashboards."""

    def list(self, request):
        months = min(max(int(request.query_params.get("months", 12)), 3), 24)
        return Response(analytics_payload(request.user, months=months))
