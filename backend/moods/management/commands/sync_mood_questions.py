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

        active_keys = set()
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
            active_keys.add(definition["key"])
            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} question {question.key}")

        # Deactivate any questions no longer in QUESTION_DEFINITIONS
        deactivated = Question.objects.filter(isActive=True).exclude(key__in=active_keys)
        count = deactivated.update(isActive=False)
        if count:
            self.stdout.write(f"Deactivated {count} removed question(s).")

        self.stdout.write(self.style.SUCCESS("Mood questions synced."))
