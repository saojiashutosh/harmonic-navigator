"""WebSocket consumer for the live group lobby and "play along" playback.

Two concerns share one socket per device on ``ws/groups/<id>/``:

* **Lobby** — every device joins the channel group ``group_<id>`` and receives
  the full serialized session whenever someone joins, marks ready, or the host
  generates the blended playlist (broadcasts fired from ``groups.views``).

* **Play along** — once the playlist exists, the host's player streams its
  state here via ``playback_control`` messages. Only the host's socket may
  send them (verified against ``?participant=<id>`` on connect); the consumer
  stores the state in Redis and fans ``playback.state`` out to the group so
  every "play along" listener stays in sync.

The connect URL carries the caller's participant id as a query parameter:
``ws/groups/<id>/?participant=<participant_id>``.
"""

import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.exceptions import ValidationError
from rest_framework.utils.encoders import JSONEncoder

from . import models, playback, realtime


class GroupSessionConsumer(AsyncJsonWebsocketConsumer):
    """Live feed of one GroupSession plus host-driven playback sync."""

    @classmethod
    async def encode_json(cls, content):
        # Payloads are already primitive (see realtime.serialize_group_payload),
        # but encode through DRF's encoder so any stray UUID/datetime is safe.
        return json.dumps(content, cls=JSONEncoder)

    async def connect(self):
        self.group_id = self.scope["url_route"]["kwargs"]["group_id"]
        params = parse_qs(self.scope.get("query_string", b"").decode())
        self.participant_id = (params.get("participant") or [None])[0]

        snapshot = await self._snapshot(self.group_id)
        if snapshot is None:
            # Unknown group — refuse the socket with a custom code so the
            # client knows not to keep retrying.
            await self.close(code=4004)
            return

        # Only the host's socket is allowed to DJ; resolve that once here.
        self.is_host = await self._is_host(self.group_id, self.participant_id)
        self.channel_group = realtime.channel_group_name(self.group_id)
        await self.channel_layer.group_add(self.channel_group, self.channel_name)
        await self.accept()

        # Send current lobby state right away so a freshly-opened view is
        # correct without waiting for the next broadcast.
        await self.send_json({"type": "group.update", "payload": snapshot})
        # ...and any in-progress play-along state, so a reconnecting listener
        # resyncs immediately rather than after the host's next heartbeat.
        state = await self._playback_state(self.group_id)
        if state is not None:
            await self.send_json({"type": "playback.state", "payload": state})

    async def disconnect(self, code):
        channel_group = getattr(self, "channel_group", None)
        if channel_group is not None:
            await self.channel_layer.group_discard(channel_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type")

        if msg_type == "ping":
            await self.send_json({"type": "pong"})

        elif msg_type == "request_playback_state":
            # A listener just toggled "play along" — hand back current state.
            state = await self._playback_state(self.group_id)
            if state is not None:
                await self.send_json({"type": "playback.state", "payload": state})

        elif msg_type == "playback_control":
            # Only the host DJs — silently ignore anyone else.
            if not getattr(self, "is_host", False):
                return
            state = await self._save_playback(self.group_id, content.get("payload") or {})
            await self.channel_layer.group_send(
                self.channel_group,
                {"type": "playback.state", "payload": state},
            )

    async def group_update(self, event):
        """Channel-layer handler for ``{"type": "group.update", ...}``."""
        await self.send_json({"type": "group.update", "payload": event["payload"]})

    async def playback_state(self, event):
        """Channel-layer handler for ``{"type": "playback.state", ...}``."""
        await self.send_json({"type": "playback.state", "payload": event["payload"]})

    # ── DB / cache helpers ──────────────────────────────────────────────

    @database_sync_to_async
    def _snapshot(self, group_id):
        group = realtime.load_group(group_id)
        if group is None:
            return None
        return realtime.serialize_group_payload(group)

    @database_sync_to_async
    def _is_host(self, group_id, participant_id):
        if not participant_id:
            return False
        try:
            return models.GroupParticipant.objects.filter(
                id=participant_id,
                groupSessionId_id=group_id,
                isHost=True,
            ).exists()
        except (ValidationError, ValueError):
            return False

    @database_sync_to_async
    def _playback_state(self, group_id):
        return playback.get_state(group_id)

    @database_sync_to_async
    def _save_playback(self, group_id, payload):
        playback.set_state(
            group_id,
            track_index=payload.get("trackIndex", 0),
            is_playing=payload.get("isPlaying", False),
            position_seconds=payload.get("positionSeconds", 0.0),
            active=payload.get("active", True),
        )
        return playback.get_state(group_id)
