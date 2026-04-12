from .views import (
    TrackFeedbackViewSet,
    UserMoodPreferenceViewSet,
    TrackMoodScoreViewSet,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'track-feedbacks', TrackFeedbackViewSet,
                basename='track-feedback')
router.register(r'user-mood-preferences',
                UserMoodPreferenceViewSet, basename='user-mood-preference')
router.register(r'track-mood-scores', TrackMoodScoreViewSet,
                basename='track-mood-score')

urlpatterns = []
urlpatterns = urlpatterns + router.urls
