from .views import (
    PlaylistViewSet,
    PlaylistTrackViewSet,
    SavedPlaylistViewSet,
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'playlists', PlaylistViewSet, basename='playlist')
router.register(r'playlist-tracks', PlaylistTrackViewSet,
                basename='playlist-track')
router.register(r'saved-playlists', SavedPlaylistViewSet,
                basename='saved-playlist')

urlpatterns = []
urlpatterns = urlpatterns + router.urls
