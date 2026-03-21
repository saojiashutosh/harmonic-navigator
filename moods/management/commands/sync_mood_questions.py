from django.core.management.base import BaseCommand, CommandError
from django.db.utils import OperationalError

from moods.constants import QUESTION_DEFINITIONS
from moods.models import Question


class Command(BaseCommand):
    help = "Create or update the default mood question catalog."

    def handle(self, *args, **options):
        try:
            Question.objects.exists()
        except OperationalError as exc:
            raise CommandError(
                "The question tables do not exist yet. Run 'python manage.py migrate' first."
            ) from exc

        for definition in QUESTION_DEFINITIONS:
            question, created = Question.objects.update_or_create(
                key=definition["key"],
                defaults={
                    "text": definition["text"],
                    "category": definition["category"],
                    "inputType": definition["inputType"],
                    "options": definition["options"],
                    "order": definition["order"],
                    "isActive": True,
                },
            )
            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} question {question.key}")

        self.stdout.write(self.style.SUCCESS("Mood questions synced."))
