from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from helpers.cache_utils import POOL_CACHE_PATTERN

from .models import Track


@receiver([post_save, post_delete], sender=Track)
def invalidate_candidate_pool_cache(sender, **kwargs):
    # Bust every cached candidate pool when tracks are added, updated, or removed
    # so the next playlist request reflects the latest track library.
    cache.delete_pattern(POOL_CACHE_PATTERN)
