from .base import *


SECRET_KEY = "test-secret-key"
DEBUG = False

INSTALLED_APPS = list(INSTALLED_APPS)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MIGRATION_MODULES = {
    "harmonic_navigator": None,
    "users": None,
    "moods": None,
    "music": None,
    "tracks": None,
    "playlists": None,
    "feedback": None,
}
