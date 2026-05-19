"""WebSocket URL routing for the group listening flow."""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # group_id is a UUID — match hex digits and hyphens.
    re_path(
        r"^ws/groups/(?P<group_id>[0-9a-fA-F-]+)/$",
        consumers.GroupSessionConsumer.as_asgi(),
    ),
]
