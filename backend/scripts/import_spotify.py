from tracks.services import import_spotify_track_url

TRACK_URL = "https://open.spotify.com/track/13KQBNW7i0LqEKZqqJbwZX?si=867ceca38ac24ea6"
METADATA = {"primaryMood": "melancholic",
            "genre": "instrumental", "language": "instrumental"}

track = import_spotify_track_url(track_url_or_id=TRACK_URL, metadata=METADATA)
print(f"Imported: id={track.id} title={track.title} mood={track.primaryMood} type={track.type} externalUrl={track.externalUrl}")
