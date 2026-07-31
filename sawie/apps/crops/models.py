"""Crop cycles planted on fields."""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

from apps.core.models import TimeStampedModel


class CropCategory(models.TextChoices):
    CEREAL = "cereal", "Cereal"
    FIBRE = "fibre", "Fibre"
    OILSEED = "oilseed", "Oilseed"
    PULSE = "pulse", "Pulse"
    FODDER = "fodder", "Fodder"
    VEGETABLE = "vegetable", "Vegetable"
    FRUIT = "fruit", "Fruit"
    SUGAR = "sugar", "Sugar"


class Season(models.TextChoices):
    KHARIF = "kharif", "Kharif"
    RABI = "rabi", "Rabi"
    ZAID = "zaid", "Zaid"
    PERENNIAL = "perennial", "Perennial"


class CropStatus(models.TextChoices):
    PLANNED = "planned", "Planned"
    GROWING = "growing", "Growing"
    HARVESTED = "harvested", "Harvested"
    FAILED = "failed", "Failed"


class Crop(TimeStampedModel):
    """One crop cycle on one field."""

    name = models.CharField(max_length=120, db_index=True)
    variety = models.CharField(max_length=120, blank=True)
    category = models.CharField(
        max_length=20, choices=CropCategory.choices, default=CropCategory.CEREAL, db_index=True
    )
    season = models.CharField(
        max_length=12, choices=Season.choices, default=Season.KHARIF, db_index=True
    )
    field = models.ForeignKey("fields.Field", on_delete=models.CASCADE, related_name="crops")
    planting_date = models.DateField(db_index=True)
    expected_harvest_date = models.DateField(null=True, blank=True)
    actual_harvest_date = models.DateField(null=True, blank=True)
    area_acres = models.DecimalField(
        "Area sown (acres)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    production_tonnes = models.DecimalField(
        "Production (tonnes)", max_digits=12, decimal_places=3, default=0,
        validators=[MinValueValidator(0)],
    )
    price_per_tonne = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)],
        help_text="Farm-gate price used for the revenue figures.",
    )
    status = models.CharField(
        max_length=12, choices=CropStatus.choices, default=CropStatus.PLANNED, db_index=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-planting_date",)
        indexes = [
            models.Index(fields=["status", "season"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        label = f"{self.name} {self.variety}".strip()
        return f"{label} — {self.field.code}"

    def get_absolute_url(self) -> str:
        return reverse("crops:detail", args=[self.pk])

    @property
    def yield_per_acre(self) -> Decimal:
        if not self.area_acres:
            return Decimal("0")
        return (self.production_tonnes / self.area_acres).quantize(Decimal("0.001"))

    @property
    def revenue(self) -> Decimal:
        return (self.production_tonnes * self.price_per_tonne).quantize(Decimal("0.01"))

    @property
    def days_to_harvest(self) -> int | None:
        if not self.expected_harvest_date:
            return None
        from django.utils import timezone

        return (self.expected_harvest_date - timezone.localdate()).days
