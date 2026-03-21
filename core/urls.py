from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('moods/', include('moods.urls')),
    path('music/', include('music.urls')),
    path('tracks/', include('tracks.urls')),
    path('playlists/', include('playlists.urls')),
    path('feedback/', include('feedback.urls')),
    path('users/', include('users.urls')),
]
