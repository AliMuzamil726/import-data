"""Create notifications and push them to connected browsers."""
from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Notification, NotificationLevel

logger = logging.getLogger("sawie.notifications")

BROADCAST_GROUP = "sawie_broadcast"


def user_group(user_id: int) -> str:
    return f"sawie_user_{user_id}"


def notify(
    title: str,
    body: str = "",
    *,
    level: str = NotificationLevel.INFO,
    url: str = "",
    category: str = "",
    recipient=None,
) -> Notification:
    """Persist a notification and push it over the channel layer."""
    notification = Notification.objects.create(
        recipient=recipient, title=title, body=body,
        level=level, url=url, category=category,
    )
    payload = notification.as_payload()
    group = user_group(recipient.id) if recipient else BROADCAST_GROUP
    try:
        channel_layer = get_channel_layer()
        if channel_layer is not None:
            async_to_sync(channel_layer.group_send)(
                group, {"type": "notification.message", "payload": payload}
            )
    except Exception:  # noqa: BLE001 - never break a request over a push failure
        logger.warning("Could not push notification %s to %s", notification.pk, group,
                       exc_info=True)
    return notification
