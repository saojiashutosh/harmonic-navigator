from django.core.management.base import BaseCommand

from tracks.models import Artist, Track


class Command(BaseCommand):
    help = "Delete all tracks and artists from the database."

    def handle(self, *args, **options):
        track_count, _ = Track.objects.all().delete()
        artist_count, _ = Artist.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {track_count} tracks and {artist_count} artists.")
        )
