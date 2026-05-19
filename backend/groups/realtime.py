"""Helpers for pushing live group-session updates over WebSockets.

This is what replaced the old frontend polling: instead of every device
re-fetching ``GET /groups/group-sessions/{id}/`` on a timer, ``views.py``
calls :func:`broadcast_group_update` after each state change and Channels
fans the new snapshot out to every device in the lobby.
"""

from __future__ import annotations

import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from rest_framework.utils.encoders import JSONEncoder

from .models import GroupSession
from .serializers import GroupSessionSerializer


def channel_group_name(group_id) -> str:
    """Name of the channel-layer group holding every device in one lobby."""
    return f"group_{group_id}"


def load_group(group_id) -> GroupSession | None:
    """Fetch a GroupSession with the same query the REST viewset uses.

    Returns ``None`` for an unknown or malformed id rather than raising, so
    callers (consumer connect, broadcast) can fail soft.
    """
    try:
        return (
            GroupSession.objects
            .select_related("playlistId", "hostId")
            .prefetch_related("participants__moodSessionId__mood_inference")
            .filter(id=group_id)
            .first()
        )
    except (ValidationError, ValueError):
        return None


def serialize_group_payload(group: GroupSession) -> dict:
    """Serialize a GroupSession into a plain, JSON/msgpack-safe dict.

    DRF's serializer leaves UUIDs and datetimes as Python objects; both the
    channel layer (msgpack) and ``json.dumps`` choke on those, so we round-trip
    through DRF's JSON encoder to flatten everything down to primitives.
    """
    data = GroupSessionSerializer(group).data
    return json.loads(json.dumps(data, cls=JSONEncoder))


def broadcast_group_update(group_id) -> None:
    """Push the current GroupSession state to every device in its lobby.

    Re-reads the session from the DB so the payload reflects writes made by
    the caller (e.g. a participant who just flipped ``isReady``). Safe to call
    even if Channels/Redis is unavailable — it simply no-ops.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    group = load_group(group_id)
    if group is None:
        return
    async_to_sync(channel_layer.group_send)(
        channel_group_name(group.id),
        {"type": "group.update", "payload": serialize_group_payload(group)},
    )
