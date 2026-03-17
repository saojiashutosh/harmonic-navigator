from .views import (
    ArtistView,
    AudioFeatureSnapshotView,
    MoodTagView,
    TrackMoodTagView,
    TrackView,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'mood-tags', MoodTagView, basename='mood-tag')
router.register(r'artists', ArtistView, basename='artist')
router.register(r'tracks', TrackView, basename='track')
router.register(r'track-mood-tags', TrackMoodTagView,
                basename='track-mood-tag')
router.register(r'audio-feature-snapshots',
                AudioFeatureSnapshotView, basename='audio-feature-snapshot')

urlpatterns = []
urlpatterns = urlpatterns + router.urls
