"""Projects — a lightweight container for programme initiatives.

Kept intentionally simple for now (name, description, status, dates, and an
optional link to fields/farmers). Richer project structure can be layered on
later without breaking this base.
"""
from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core.models import TimeStampedModel


class ProjectStatus(models.TextChoices):
    PLANNING = "planning", "Planning"
    ACTIVE = "active", "Active"
    ON_HOLD = "on_hold", "On hold"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class Project(TimeStampedModel):
    """A programme or initiative that groups work together."""

    name = models.CharField(max_length=160, db_index=True)
    code = models.CharField(max_length=40, blank=True, help_text="Optional short reference.")
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=12, choices=ProjectStatus.choices,
        default=ProjectStatus.PLANNING, db_index=True,
    )
    location = models.CharField(max_length=160, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    lead = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="led_projects", limit_choices_to={"is_active": True},
    )
    budget = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Optional. Total planned budget.",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("projects:detail", args=[self.pk])

    @property
    def status_colour(self) -> str:
        return {
            ProjectStatus.PLANNING: "#9C7B4F",
            ProjectStatus.ACTIVE: "#5C8A34",
            ProjectStatus.ON_HOLD: "#F59E0B",
            ProjectStatus.COMPLETED: "#3B5A22",
            ProjectStatus.CANCELLED: "#DC2626",
        }.get(self.status, "#94A3B8")
