"""Farmer registry."""
import re

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.urls import reverse

from apps.core.models import TimeStampedModel

CNIC_VALIDATOR = RegexValidator(
    regex=r"^\d{5}-\d{7}-\d$",
    message="Enter the CNIC as 13 digits in the format 00000-0000000-0.",
)
PHONE_VALIDATOR = RegexValidator(
    regex=r"^[0-9+\-\s()]{7,20}$",
    message="Enter a valid phone number.",
)


class FarmerStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    PENDING = "pending", "Pending verification"


class Farmer(TimeStampedModel):
    """A registered grower. One farmer owns many fields."""

    sawie_id = models.CharField(
        "SAWiE ID", max_length=12, unique=True, blank=True, db_index=True,
        help_text="Auto-generated unique ID (e.g. SW1101).",
    )
    full_name = models.CharField(max_length=150, db_index=True)
    father_name = models.CharField(max_length=150, blank=True)
    cnic = models.CharField(
        "CNIC", max_length=15, unique=True, validators=[CNIC_VALIDATOR],
        help_text="Format: 00000-0000000-0",
    )
    phone = models.CharField(max_length=20, validators=[PHONE_VALIDATOR])
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    village = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, db_index=True)
    district = models.CharField(max_length=120, blank=True, db_index=True)
    province = models.CharField(max_length=120, blank=True, default="Punjab")
    profile_image = models.ImageField(upload_to="farmers/", blank=True, null=True)
    total_land_acres = models.DecimalField(
        "Total land (acres)", max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    registration_date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=10, choices=FarmerStatus.choices, default=FarmerStatus.ACTIVE, db_index=True
    )
    notes = models.TextField(blank=True)
    portal_user = models.OneToOneField(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="farmer_profile",
        help_text="Optional login so the farmer can see their own fields.",
    )

    class Meta:
        ordering = ("full_name",)
        indexes = [
            models.Index(fields=["status", "city"]),
            models.Index(fields=["registration_date"]),
        ]

    def __str__(self) -> str:
        return self.full_name

    def get_absolute_url(self) -> str:
        return reverse("farmers:detail", args=[self.pk])

    SAWIE_ID_START = 1101  # first ID is SW1101

    def save(self, *args, **kwargs):
        if not self.sawie_id:
            self.sawie_id = self._next_sawie_id()
        super().save(*args, **kwargs)

    @classmethod
    def _next_sawie_id(cls) -> str:
        """Return the next SWxxxx id, continuing from the highest existing one."""
        last = (
            cls.objects.exclude(sawie_id="")
            .filter(sawie_id__startswith="SW")
            .order_by("-sawie_id")
            .values_list("sawie_id", flat=True)
            .first()
        )
        if last:
            try:
                n = int(last[2:]) + 1
            except (ValueError, TypeError):
                n = cls.SAWIE_ID_START
        else:
            n = cls.SAWIE_ID_START
        # Ensure uniqueness even if there are gaps/duplicates.
        while cls.objects.filter(sawie_id=f"SW{n}").exists():
            n += 1
        return f"SW{n}"

    def clean(self):
        super().clean()
        if self.cnic:
            digits = re.sub(r"\D", "", self.cnic)
            if len(digits) == 13:
                self.cnic = f"{digits[:5]}-{digits[5:12]}-{digits[12]}"
            else:
                raise ValidationError({"cnic": "A CNIC must contain exactly 13 digits."})

    @property
    def mapped_area(self):
        """Area actually drawn on the map, which may differ from declared land."""
        return sum((f.area_acres for f in self.fields.all()), start=0)

    @property
    def initials(self) -> str:
        parts = self.full_name.split()
        return "".join(p[0] for p in parts[:2]).upper() or "F"
