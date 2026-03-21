from rest_framework.routers import DefaultRouter

from .views import MusicTrackViewSet

router = DefaultRouter()
router.register(r"tracks", MusicTrackViewSet, basename="music-track")

urlpatterns = []
urlpatterns = urlpatterns + router.urls
