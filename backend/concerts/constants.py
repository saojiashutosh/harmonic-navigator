# Default number of tracks in a generated "get ready for the concert" playlist.
DEFAULT_CONCERT_PLAYLIST_SIZE = 25

# Maximum distinct setlist songs kept per artist when aggregating recent shows.
SETLIST_SONG_LIMIT = 40

# Moods used to fill a concert-prep playlist when the artist's own catalog is
# too thin to reach the target size — live shows skew high-energy.
CONCERT_FILLER_MOODS = ("energized", "celebratory")

# moodLabel stamped on Playlist rows created by Concert Mode.
CONCERT_MOOD_LABEL = "concert"
