"""Smoke test for the group-lobby WebSocket consumer.

Connects to GroupSessionConsumer, asserts it gets the initial snapshot, then
fires a broadcast and asserts it arrives live. Run inside the web container:

    docker compose exec web python scripts/ws_smoke.py <group_id>
"""

import asyncio
import os
import sys

import django

# Allow running as `python scripts/ws_smoke.py` — put the project root (the
# parent of this file's directory) on the path so `core`/`groups` import.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.development")
django.setup()

from channels.testing import WebsocketCommunicator  # noqa: E402

from core.asgi import application  # noqa: E402
from groups.realtime import broadcast_group_update  # noqa: E402


async def main(group_id: str) -> None:
    communicator = WebsocketCommunicator(application, f"/ws/groups/{group_id}/")
    connected, _ = await communicator.connect()
    assert connected, "WebSocket failed to connect"
    print("connected OK")

    snapshot = await communicator.receive_json_from()
    assert snapshot["type"] == "group.update", snapshot
    assert snapshot["payload"]["id"] == group_id, snapshot
    print(f"initial snapshot OK — {len(snapshot['payload']['participants'])} participant(s)")

    # A broadcast (as views.py fires) must reach the open socket.
    await asyncio.get_event_loop().run_in_executor(
        None, broadcast_group_update, group_id
    )
    pushed = await communicator.receive_json_from()
    assert pushed["type"] == "group.update", pushed
    print("live broadcast received OK")

    await communicator.disconnect()
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/ws_smoke.py <group_id>")
    asyncio.run(main(sys.argv[1]))
