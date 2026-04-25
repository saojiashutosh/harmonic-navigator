from django.core.management.base import BaseCommand

from helpers.excel_storage import export_tracks_to_excel
from tracks.models import Track


class Command(BaseCommand):
    help = "Export every stored track into the single song storage Excel workbook."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=None,
            help="Optional workbook path. Defaults to SONG_EXCEL_BACKUP_PATH.",
        )

    def handle(self, *args, **options):
        path = export_tracks_to_excel(path=options["path"])
        count = Track.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Exported {count} tracks to {path}"))
