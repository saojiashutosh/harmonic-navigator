from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from helpers.cache_utils import QUESTIONS_CACHE_KEY

from .models import Question


@receiver([post_save, post_delete], sender=Question)
def invalidate_questions_cache(sender, **kwargs):
    cache.delete(QUESTIONS_CACHE_KEY)
