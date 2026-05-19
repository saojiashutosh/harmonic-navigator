"""Shared "play along" playback state for a group session.

When the host is DJ-ing, their player's state — which track, playing or
paused, and how far in — is mirrored here so any participant who toggles
"play along" can snap to the exact moment the rest of the group is hearing.

State lives in Redis (the Django cache) rather than the database: it changes
several times a minute, never needs to outlive the session, and a finished
session's playback position is meaningless. If Redis is down the cache is
configured to fail soft, so play-along simply goes quiet rather than erroring.
"""

import time

from django.core.cache import cache

# Comfortably past a session's useful life (GROUP_TTL_HOURS is 24h, but
# playback only matters while people are actively listening).
_TTL_SECONDS = 60 * 60 * 12
_KEY = "group_playback:{}"


def _key(group_id) -> str:
    return _KEY.format(group_id)


def get_state(group_id) -> dict | None:
    """Return the shared playback state extrapolated to *now*.

    ``None`` means the host has never started DJ-ing this session. When the
    host is playing, ``positionSeconds`` is advanced by the wall-clock time
    elapsed since the host last reported in, so a listener joining mid-song
    lands on the live position rather than a stale one.
    """
    state = cache.get(_key(group_id))
    if not state:
        return None

    now = time.time()
    position = state["positionSeconds"]
    if state["isPlaying"] and state["active"]:
        position += max(0.0, now - state["updatedAt"])

    return {
        "trackIndex": state["trackIndex"],
        "isPlaying": state["isPlaying"],
        "active": state["active"],
        "positionSeconds": round(position, 3),
        "serverTimeMs": int(now * 1000),
    }


def set_state(group_id, *, track_index, is_playing, position_seconds, active) -> None:
    """Persist the host's current playback state.

    Inputs come straight off a WebSocket message, so values are coerced
    defensively — a malformed frame degrades to a sane default instead of
    raising and dropping the socket.
    """
    try:
        track_index = max(0, int(track_index))
    except (TypeError, ValueError):
        track_index = 0
    try:
        position_seconds = max(0.0, float(position_seconds))
    except (TypeError, ValueError):
        position_seconds = 0.0

    cache.set(
        _key(group_id),
        {
            "trackIndex": track_index,
            "isPlaying": bool(is_playing),
            "active": bool(active),
            "positionSeconds": position_seconds,
            "updatedAt": time.time(),
        },
        timeout=_TTL_SECONDS,
    )
