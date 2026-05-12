from django.apps import AppConfig


class TracksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tracks'

    def ready(self):
        import tracks.signals  # noqa: F401
