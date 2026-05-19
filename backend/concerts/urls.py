from rest_framework.routers import DefaultRouter

from .views import ConcertEventViewSet, ConcertPlaylistViewSet

router = DefaultRouter()
router.register(r'events', ConcertEventViewSet, basename='concert-event')
router.register(
    r'concert-playlists', ConcertPlaylistViewSet, basename='concert-playlist',
)

urlpatterns = []
urlpatterns = urlpatterns + router.urls
