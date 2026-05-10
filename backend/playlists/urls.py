from .views import (
    PlaylistViewSet,
    PlaylistTrackViewSet,
    SavedPlaylistViewSet,
    youtube_search,
    saavn_search,
)
from rest_framework.routers import DefaultRouter
from django.urls import path

router = DefaultRouter()
router.register(r'playlists', PlaylistViewSet, basename='playlist')
router.register(r'playlist-tracks', PlaylistTrackViewSet,
                basename='playlist-track')
router.register(r'saved-playlists', SavedPlaylistViewSet,
                basename='saved-playlist')

urlpatterns = [
    path('youtube-search/', youtube_search, name='youtube-search'),
    path('saavn-search/', saavn_search, name='saavn-search'),
]
urlpatterns = urlpatterns + router.urls
