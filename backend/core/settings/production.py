from .base import *


DEBUG = env_bool("DJANGO_DEBUG", False)

SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# HF Spaces (and most PaaS) terminate TLS at a reverse proxy and forward plain
# HTTP with X-Forwarded-Proto. Without this Django thinks the request is
# insecure and breaks secure-cookie + HTTPS redirect logic behind the proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Serve static files (Django admin/DRF assets) directly from Daphne via
# WhiteNoise — there is no nginx in front on HF Spaces. Insert immediately
# after SecurityMiddleware as WhiteNoise requires.
MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
