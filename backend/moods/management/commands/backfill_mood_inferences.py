"""
Backfill existing MoodInference records with secondaryMoodLabel,
secondaryConfidence, and moodBlendRatio using the upgraded inference engine.
"""

from django.core.management.base import BaseCommand

from moods.constants import QUESTION_DEFINITIONS
from moods.inference import build_weight_key, infer_mood_from_responses
from moods.models import MoodInference


# Category map from definitions (avoids DB query)
_CATEGORY_MAP = {d["key"]: d["category"] for d in QUESTION_DEFINITIONS}


class Command(BaseCommand):
    help = "Re-run the inference engine on all existing MoodInference records to populate new fields."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without writing to the DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        inferences = (
            MoodInference.objects.select_related("moodSessionId")
            .prefetch_related("moodSessionId__answer__questionId")
            .all()
        )

        updated_count = 0
        skipped_count = 0

        for inference in inferences:
            session = inference.moodSessionId
            answers = session.answer.select_related("questionId").all()

            if not answers.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipping inference {inference.id} — no answers in session {session.id}"
                    )
                )
                skipped_count += 1
                continue

            responses = [
                {
                    "weight_key": build_weight_key(a.questionId, a.rawValue),
                    "value": a.value,
                    "raw_value": a.rawValue,
                    "category": a.questionId.category,
                }
                for a in answers
            ]

            (
                top_mood,
                secondary_mood,
                confidence,
                secondary_confidence,
                mood_blend_ratio,
                probabilities,
            ) = infer_mood_from_responses(
                responses,
                question_categories=_CATEGORY_MAP,
            )

            label = (
                f"  Inference {inference.id}: "
                f"{inference.moodLabel}({inference.confidence:.2f}) → "
                f"{top_mood}({confidence:.2f}) + "
                f"{secondary_mood}({secondary_confidence:.2f}) "
                f"blend={mood_blend_ratio:.2f}"
            )

            if dry_run:
                self.stdout.write(label)
            else:
                inference.moodLabel = top_mood
                inference.confidence = confidence
                inference.rawScores = probabilities
                inference.secondaryMoodLabel = secondary_mood
                inference.secondaryConfidence = secondary_confidence
                inference.moodBlendRatio = mood_blend_ratio
                inference.save(
                    update_fields=[
                        "moodLabel",
                        "confidence",
                        "rawScores",
                        "secondaryMoodLabel",
                        "secondaryConfidence",
                        "moodBlendRatio",
                    ]
                )
                self.stdout.write(label)
                updated_count += 1

        action = "Would update" if dry_run else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{action} {updated_count} inference(s), skipped {skipped_count}."
            )
        )
