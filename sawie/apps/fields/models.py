"""Field (plot) registry with GIS geometry stored as GeoJSON."""
import json

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from apps.core.models import TimeStampedModel


class SoilType(models.TextChoices):
    SANDY = "sandy", "Sandy"
    LOAM = "loam", "Loam"
    SANDY_LOAM = "sandy_loam", "Sandy loam"
    CLAY_LOAM = "clay_loam", "Clay loam"
    CLAY = "clay", "Clay"
    SILT = "silt", "Silt"
    SALINE = "saline", "Saline / sodic"


class IrrigationType(models.TextChoices):
    CANAL = "canal", "Canal"
    TUBEWELL = "tubewell", "Tubewell"
    DRIP = "drip", "Drip"
    SPRINKLER = "sprinkler", "Sprinkler"
    RAINFED = "rainfed", "Rainfed"
    MIXED = "mixed", "Canal + tubewell"


class FieldStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    FALLOW = "fallow", "Fallow"
    HARVESTED = "harvested", "Harvested"
    RETIRED = "retired", "Retired"


class HealthBand(models.TextChoices):
    HEALTHY = "healthy", "Healthy"
    MODERATE = "moderate", "Moderate"
    POOR = "poor", "Poor"
    CRITICAL = "critical", "Critical"
    UNKNOWN = "unknown", "Not assessed"


class Field(TimeStampedModel):
    """A mapped plot belonging to a farmer."""

    name = models.CharField(max_length=150, db_index=True)
    code = models.CharField(max_length=40, unique=True, help_text="Unique plot reference.")
    farmer = models.ForeignKey(
        "farmers.Farmer", on_delete=models.CASCADE, related_name="fields"
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    boundary = models.JSONField(
        blank=True, null=True,
        help_text="GeoJSON Polygon drawn on the map. Stored as {'type': 'Polygon', ...}.",
    )
    area_acres = models.DecimalField(
        "Area (acres)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    soil_type = models.CharField(max_length=20, choices=SoilType.choices, default=SoilType.LOAM)
    irrigation_type = models.CharField(
        max_length=20, choices=IrrigationType.choices, default=IrrigationType.CANAL
    )
    status = models.CharField(
        max_length=12, choices=FieldStatus.choices, default=FieldStatus.ACTIVE, db_index=True
    )
    health = models.CharField(
        max_length=12, choices=HealthBand.choices, default=HealthBand.UNKNOWN, db_index=True
    )
    latest_ndvi = models.FloatField(null=True, blank=True)
    ndvi_updated_at = models.DateTimeField(null=True, blank=True)
    officer = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assigned_fields", limit_choices_to={"is_active": True},
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["farmer", "status"]),
            models.Index(fields=["health"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def get_absolute_url(self) -> str:
        return reverse("fields:detail", args=[self.pk])

    def clean(self):
        super().clean()
        if self.boundary:
            geometry = self.boundary
            if isinstance(geometry, str):
                try:
                    geometry = json.loads(geometry)
                except json.JSONDecodeError as exc:
                    raise ValidationError({"boundary": "Boundary is not valid JSON."}) from exc
                self.boundary = geometry
            if geometry.get("type") != "Polygon" or not geometry.get("coordinates"):
                raise ValidationError(
                    {"boundary": "Boundary must be a GeoJSON Polygon with coordinates."}
                )

    @property
    def current_crop(self):
        return self.crops.filter(status__in=["planned", "growing"]).order_by("-planting_date").first()

    @property
    def health_colour(self) -> str:
        return {
            HealthBand.HEALTHY: "#2E7D32",
            HealthBand.MODERATE: "#F59E0B",
            HealthBand.POOR: "#EA580C",
            HealthBand.CRITICAL: "#DC2626",
        }.get(self.health, "#94A3B8")

    def as_geojson_feature(self) -> dict:
        """Serialise for Leaflet: polygon when drawn, otherwise a point marker.

        Coordinates are guarded so a field with a NULL/blank lat or lng never
        produces ``None`` values that would crash the map JavaScript.
        """
        crop = self.current_crop
        lat = float(self.latitude) if self.latitude is not None else None
        lng = float(self.longitude) if self.longitude is not None else None

        geometry = self.boundary
        if not geometry and lat is not None and lng is not None:
            geometry = {"type": "Point", "coordinates": [lng, lat]}

        return {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": self.pk,
                "name": self.name,
                "code": self.code,
                "farmer": self.farmer.full_name,
                "farmer_id": self.farmer_id,
                "area": float(self.area_acres) if self.area_acres is not None else 0,
                "soil": self.get_soil_type_display(),
                "irrigation": self.get_irrigation_type_display(),
                "status": self.status,
                "health": self.health,
                "colour": self.health_colour,
                "ndvi": self.latest_ndvi,
                "crop": crop.name if crop else "",
                "crop_id": crop.pk if crop else None,
                "lat": lat,
                "lng": lng,
                "url": self.get_absolute_url(),
            },
        }


class FarmActivity(TimeStampedModel):
    """Field operations log: sowing, irrigation, spraying, harvest and so on."""

    class Kind(models.TextChoices):
        LAND_PREP = "land_prep", "Land preparation"
        SOWING = "sowing", "Sowing"
        IRRIGATION = "irrigation", "Irrigation"
        FERTILISER = "fertiliser", "Fertiliser"
        PESTICIDE = "pesticide", "Crop protection"
        SCOUTING = "scouting", "Scouting"
        HARVEST = "harvest", "Harvest"
        OTHER = "other", "Other"

    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name="activities")
    crop = models.ForeignKey(
        "crops.Crop", null=True, blank=True, on_delete=models.SET_NULL, related_name="activities"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OTHER)
    performed_on = models.DateField(db_index=True)
    detail = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=20, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ("-performed_on",)
        verbose_name_plural = "farm activities"

    def __str__(self) -> str:
        return f"{self.get_kind_display()} on {self.field.code} ({self.performed_on})"
