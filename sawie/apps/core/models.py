"""Shared base models and the notification store."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Adds created/updated timestamps and the user who created the row."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        abstract = True


class NotificationLevel(models.TextChoices):
    INFO = "info", "Info"
    SUCCESS = "success", "Success"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"


class NotificationQuerySet(models.QuerySet):
    def for_user(self, user):
        """Personal alerts plus broadcasts (recipient is NULL)."""
        return self.filter(models.Q(recipient=user) | models.Q(recipient__isnull=True))


class Notification(models.Model):
    """A single in-app alert, pushed to the browser over WebSockets."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="notifications",
        help_text="Leave empty to broadcast to every signed-in user.",
    )
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    level = models.CharField(
        max_length=10, choices=NotificationLevel.choices, default=NotificationLevel.INFO
    )
    url = models.CharField(max_length=300, blank=True)
    category = models.CharField(max_length=40, blank=True, db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self) -> str:
        return self.title

    def as_payload(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "level": self.level,
            "url": self.url,
            "category": self.category,
            "created_at": timezone.localtime(self.created_at).strftime("%d %b %Y, %H:%M"),
        }
