"""Domain events that raise notifications."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from apps.crops.models import Crop, CropStatus
from apps.farmers.models import Farmer
from apps.fields.models import Field

from .models import NotificationLevel
from .notifications import notify


@receiver(post_save, sender=Farmer)
def farmer_registered(sender, instance: Farmer, created: bool, **kwargs):
    if created:
        notify(
            "New farmer registered",
            f"{instance.full_name} joined from {instance.city or 'an unspecified city'}.",
            level=NotificationLevel.SUCCESS,
            url=reverse("farmers:detail", args=[instance.pk]),
            category="farmers",
        )


@receiver(post_save, sender=Field)
def field_health_changed(sender, instance: Field, created: bool, **kwargs):
    if created:
        notify(
            "Field mapped",
            f"{instance.name} ({instance.area_acres} ac) added for {instance.farmer.full_name}.",
            level=NotificationLevel.INFO,
            url=reverse("fields:detail", args=[instance.pk]),
            category="fields",
        )
    elif instance.health in {"poor", "critical"}:
        notify(
            f"{instance.get_health_display()} vegetation on {instance.code}",
            f"NDVI for {instance.name} is {instance.latest_ndvi:.2f}."
            if instance.latest_ndvi is not None else "Latest scene flagged this field.",
            level=NotificationLevel.CRITICAL if instance.health == "critical"
            else NotificationLevel.WARNING,
            url=reverse("fields:detail", args=[instance.pk]),
            category="ndvi",
        )


@receiver(post_save, sender=Crop)
def crop_harvest_logged(sender, instance: Crop, created: bool, **kwargs):
    if not created and instance.status == CropStatus.HARVESTED and instance.production_tonnes:
        notify(
            "Harvest recorded",
            f"{instance.name} on {instance.field.code}: "
            f"{instance.production_tonnes} t ({instance.yield_per_acre} t/ac).",
            level=NotificationLevel.SUCCESS,
            url=reverse("crops:detail", args=[instance.pk]),
            category="crops",
        )
