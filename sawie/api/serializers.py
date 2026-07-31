"""REST serializers."""
from rest_framework import serializers

from apps.core.models import Notification
from apps.crops.models import Crop
from apps.farmers.models import Farmer
from apps.fields.models import FarmActivity, Field
from apps.ndvi.models import NDVIRecord
from apps.weather.models import WeatherData


class FarmerSerializer(serializers.ModelSerializer):
    field_count = serializers.IntegerField(source="fields.count", read_only=True)

    class Meta:
        model = Farmer
        fields = (
            "id", "full_name", "father_name", "cnic", "phone", "email", "address",
            "village", "city", "district", "province", "total_land_acres",
            "registration_date", "status", "field_count", "created_at",
        )
        read_only_fields = ("created_at",)


class FieldSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source="farmer.full_name", read_only=True)
    current_crop = serializers.SerializerMethodField()

    class Meta:
        model = Field
        fields = (
            "id", "code", "name", "farmer", "farmer_name", "latitude", "longitude",
            "boundary", "area_acres", "soil_type", "irrigation_type", "status",
            "health", "latest_ndvi", "ndvi_updated_at", "current_crop", "created_at",
        )
        read_only_fields = ("latest_ndvi", "ndvi_updated_at", "created_at")

    def get_current_crop(self, obj) -> str:
        crop = obj.current_crop
        return crop.name if crop else ""


class CropSerializer(serializers.ModelSerializer):
    field_code = serializers.CharField(source="field.code", read_only=True)
    yield_per_acre = serializers.DecimalField(max_digits=10, decimal_places=3, read_only=True)
    revenue = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Crop
        fields = (
            "id", "name", "variety", "category", "season", "field", "field_code",
            "planting_date", "expected_harvest_date", "actual_harvest_date",
            "area_acres", "production_tonnes", "price_per_tonne", "yield_per_acre",
            "revenue", "status",
        )


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = FarmActivity
        fields = ("id", "field", "crop", "kind", "performed_on", "detail",
                  "quantity", "unit", "cost")


class NDVISerializer(serializers.ModelSerializer):
    field_code = serializers.CharField(source="field.code", read_only=True)

    class Meta:
        model = NDVIRecord
        fields = (
            "id", "field", "field_code", "captured_on", "source", "index_used",
            "mean_index", "min_index", "max_index", "healthy_pct", "moderate_pct",
            "poor_pct", "critical_pct", "health_score", "status", "overlay",
        )
        read_only_fields = fields


class WeatherSerializer(serializers.ModelSerializer):
    field_code = serializers.CharField(source="field.code", read_only=True)

    class Meta:
        model = WeatherData
        fields = (
            "id", "field", "field_code", "fetched_at", "temperature_c", "humidity_pct",
            "rain_probability_pct", "precipitation_mm", "wind_speed_kmh", "uv_index",
            "condition_text", "forecast",
        )
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "title", "body", "level", "url", "category", "is_read", "created_at")
        read_only_fields = ("created_at",)
