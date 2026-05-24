# Default number of tracks in a generated "get ready for the concert" playlist.
DEFAULT_CONCERT_PLAYLIST_SIZE = 25

# Maximum distinct setlist songs kept per artist when aggregating recent shows.
SETLIST_SONG_LIMIT = 40

# moodLabel stamped on Playlist rows created by Concert Mode.
CONCERT_MOOD_LABEL = "concert"

# Minimum normalised artist-name length eligible for word-boundary matching
# against event titles — shorter names cause false-positive substring hits.
MIN_ARTIST_MATCH_LENGTH = 4

# How many JioSaavn search results to pull when topping up a concert artist
# whose local catalog is too thin to fill the playlist.
ONLINE_FETCH_LIMIT = 80

# Concert playlists recommend Bollywood (Hindi) and Marathi songs only.
CONCERT_LANGUAGES = ("hindi", "marathi")

# Devotional / spiritual songs are kept out of concert playlists — matched as
# case-insensitive substrings of a track's title or genre.
DEVOTIONAL_KEYWORDS = (
    "bhajan", "aarti", "kirtan", "mantra", "chalisa", "stotra", "stotram",
    "shloka", "shlok", "bhakti", "bhaktigeet", "abhang", "abhanga",
    "vandana", "qawwali", "devotional", "spiritual", "naamsmaran",
)

