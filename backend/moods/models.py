from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from users.models import Users
from harmonic_navigator.models import HarmonicBaseModel


class MoodSession(HarmonicBaseModel):
    userId = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name="mood_sessions",
        verbose_name=_("User"),
        db_column="userId",
        null=True,
    )

    startedAt = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Started at"),
        null=True,
        db_column="startedAt",
    )

    endedAt = models.DateTimeField(
        verbose_name=_("Ended at"),
        null=True,
        db_column="endedAt",
    )

    durationSeconds = models.PositiveIntegerField(
        verbose_name=_("Duration Seconds"),
        null=True,
        db_column="durationSeconds",
    )

    class Meta:
        db_table = "mood_session"
        verbose_name = "Mood Session"
        verbose_name_plural = "Mood Sessions"
        managed = True

    def __str__(self):
        return f"{self.id}"

    @property
    def duration_seconds(self):
        if self.startedAt and self.endedAt:
            return int((self.endedAt - self.startedAt).total_seconds())
        return None


class Question(HarmonicBaseModel):

    class CategoryChoices(models.TextChoices):
        ENERGY = "energy", "Energy"
        EMOTION = "emotion", "Emotion"
        COGNITION = "cognition", "Cognition"
        ACTIVITY = "activity", "Activity"
        CONTEXT = "context", "Context"
        PREFERENCE = "preference", "Preference"

    class InputTypeChoices(models.TextChoices):
        SELECT = "select", "Select"
        TEXT = "text", "Text"

    key = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_("Key"),
        db_column="key",
    )

    text = models.CharField(
        max_length=255,
        verbose_name=_("Text"),
        db_column="text",
        null=True,
    )

    category = models.CharField(
        max_length=32,
        choices=CategoryChoices.choices,
        null=True,
        verbose_name=_("Category"),
        db_column="category",
    )

    inputType = models.CharField(
        max_length=16,
        choices=InputTypeChoices.choices,
        default=InputTypeChoices.SELECT,
        verbose_name=_("Input Type"),
        db_column="input_type",
    )

    options = models.JSONField(
        default=list,
        verbose_name=_("Options"),
    )

    order = models.PositiveIntegerField(
        null=True,
        verbose_name=_("Order"),
    )

    isActive = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        db_column="is_active",
    )

    class Meta:
        db_table = "mood_questions"
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        managed = True

    def __str__(self):
        return f"{self.id}"


class Answer(HarmonicBaseModel):

    moodSessionId = models.ForeignKey(
        MoodSession,
        on_delete=models.CASCADE,
        related_name="answer",
        db_column="mood_session_id",
        verbose_name=_("Mood Session Id"),
    )

    questionId = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="answers",
        db_column="question_id",
        verbose_name=_("Question Id"),
    )

    rawValue = models.CharField(
        max_length=64,
        null=True,
        verbose_name=_("Raw Value"),
        db_column="raw_value",
    )

    value = models.FloatField(
        validators=[
            MinValueValidator(0.0),
            MaxValueValidator(1.0),
        ],
        default=0.5,
        verbose_name=_("Value"),
        db_column="value",
    )

    class Meta:
        db_table = "mood_question_answers"
        verbose_name = "Answer"
        verbose_name_plural = "Answers"
        managed = True

    def __str__(self):
        return f"{self.id}"


class MoodInference(HarmonicBaseModel):

    class MoodChoices(models.TextChoices):
        ENERGIZED = "energized", "Energized"
        FOCUSED = "focused", "Focused"
        MELANCHOLIC = "melancholic", "Melancholic"
        ANXIOUS = "anxious", "Anxious"
        CELEBRATORY = "celebratory", "Celebratory"
        CALM = "calm", "Calm"

    moodSessionId = models.OneToOneField(
        MoodSession,
        on_delete=models.CASCADE,
        related_name="mood_inference",
        db_column="mood_session_id",
        verbose_name=_("Mood Session"),
    )

    moodLabel = models.CharField(
        max_length=32,
        choices=MoodChoices.choices,
        null=True,
        verbose_name=_("Mood Label"),
        db_column="mood_label",
    )

    confidence = models.FloatField(
        validators=[
            MinValueValidator(0.0),
            MaxValueValidator(1.0),
        ],
        default=0.0,
        verbose_name=_("Confidence"),
        db_column="confidence",
    )

    rawScores = models.JSONField(
        default=dict,
        verbose_name=_("Raw Scores"),
        db_column="raw_scores",
    )

    class Meta:
        db_table = "mood_inferences"
        verbose_name = "Mood Inference"
        verbose_name_plural = "Mood Inferences"

    def __str__(self):
        return f"{self.id}"

    @property
    def is_high_confidence(self):
        return self.confidence >= 0.70
