"""WebSocket consumer for the live group lobby.

Replaces the old 2.5s frontend polling. Every device viewing a group session
opens ``ws/groups/<id>/`` and joins the channel group ``group_<id>``. It then
receives the full serialized session whenever someone joins, marks themselves
ready, or the host generates the blended playlist — broadcasts fired from
``groups.views`` via :func:`groups.realtime.broadcast_group_update`.

Clients only listen; the consumer accepts a ``ping`` purely to keep idle
intermediaries from closing the socket.
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework.utils.encoders import JSONEncoder

from . import realtime


class GroupSessionConsumer(AsyncJsonWebsocketConsumer):
    """Read-only live feed of a single GroupSession."""

    @classmethod
    async def encode_json(cls, content):
        # Payloads are already primitive (see realtime.serialize_group_payload),
        # but encode through DRF's encoder so any stray UUID/datetime is safe.
        return json.dumps(content, cls=JSONEncoder)

    async def connect(self):
        self.group_id = self.scope["url_route"]["kwargs"]["group_id"]
        snapshot = await self._snapshot(self.group_id)
        if snapshot is None:
            # Unknown group — refuse the socket with a custom code so the
            # client knows not to keep retrying.
            await self.close(code=4004)
            return

        self.channel_group = realtime.channel_group_name(self.group_id)
        await self.channel_layer.group_add(self.channel_group, self.channel_name)
        await self.accept()
        # Send current state right away so a freshly-opened lobby is correct
        # without waiting for the next broadcast.
        await self.send_json({"type": "group.update", "payload": snapshot})

    async def disconnect(self, code):
        channel_group = getattr(self, "channel_group", None)
        if channel_group is not None:
            await self.channel_layer.group_discard(channel_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def group_update(self, event):
        """Channel-layer handler for ``{"type": "group.update", ...}``."""
        await self.send_json({"type": "group.update", "payload": event["payload"]})

    @database_sync_to_async
    def _snapshot(self, group_id):
        group = realtime.load_group(group_id)
        if group is None:
            return None
        return realtime.serialize_group_payload(group)
