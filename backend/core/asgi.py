"""
ASGI config for core project.

It exposes the ASGI callable as a module-level variable named ``application``.

HTTP requests are served by the standard Django app; ``ws://`` connections are
routed to Channels consumers (see ``groups/routing.py``).

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')

# Initialise the Django ASGI application early so the app registry is fully
# populated before importing consumers (which touch models).
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from groups.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(websocket_urlpatterns),
})
