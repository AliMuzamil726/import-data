"""WebSocket URL routing."""
from django.urls import path

from apps.core.consumers import NotificationConsumer

websocket_urlpatterns = [
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
