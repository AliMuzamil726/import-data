"""WebSocket consumer for live notifications."""
import json

from channels.generic.websocket import AsyncWebsocketConsumer

from .notifications import BROADCAST_GROUP, user_group


class NotificationConsumer(AsyncWebsocketConsumer):
    """Joins each signed-in user to their private group plus the broadcast group."""

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.groups_joined = [BROADCAST_GROUP, user_group(user.id)]
        for group in self.groups_joined:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()
        await self.send(json.dumps({"type": "ready"}))

    async def disconnect(self, code):
        for group in getattr(self, "groups_joined", []):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Client only sends keep-alive pings.
        if text_data and text_data.strip() == "ping":
            await self.send("pong")

    async def notification_message(self, event):
        await self.send(json.dumps({"type": "notification", "data": event["payload"]}))
