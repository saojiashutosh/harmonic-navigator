DEFAULT_PLAYLIST_SIZE = 20
GUEST_PLAYLIST_SIZE = 15        # max tracks for anonymous users
REGISTERED_PLAYLIST_SIZE = 60   # tracks for logged-in users
EXPAND_COUNT = 40               # extra tracks added via expand

MOOD_TYPE_RATIOS = {
    "energized": {"song": 0.65, "instrumental": 0.25, "ambient": 0.10},
    "celebratory": {"song": 0.75, "instrumental": 0.15, "ambient": 0.10},
    "focused": {"song": 0.20, "instrumental": 0.60, "ambient": 0.20},
    "calm": {"song": 0.20, "instrumental": 0.35, "ambient": 0.45},
    "melancholic": {"song": 0.45, "instrumental": 0.25, "ambient": 0.30},
    "anxious": {"song": 0.20, "instrumental": 0.35, "ambient": 0.45},
}

TARGET_TRACK_ATTRIBUTES = {
    "energized": {"energy": 0.85, "valence": 0.75},
    "celebratory": {"energy": 0.90, "valence": 0.90},
    "focused": {"energy": 0.55, "valence": 0.45},
    "calm": {"energy": 0.20, "valence": 0.50},
    "melancholic": {"energy": 0.30, "valence": 0.25},
    "anxious": {"energy": 0.25, "valence": 0.20},
}

# Era inference for tracks with missing releaseYear. Maps artist name to the
# era their catalog belongs to. Used by the recommendation engine when a track
# has releaseYear=NULL (typically because Spotify returned a remaster/compilation
# year and it was nulled out) — the engine treats the track as belonging to the
# artist's era for era-filtered playlists.
ARTIST_ERA = {
    # Nineties Bollywood / Indian playback
    "Kumar Sanu": "nineties",
    "K. S. Chithra": "nineties",
    "Chitra": "nineties",
    "Udit Narayan": "nineties",
    "Alka Yagnik": "nineties",
    "Kavita Krishnamurthy": "nineties",
    "Sadhana Sargam": "nineties",
    "Anuradha Paudwal": "nineties",
    "Poornima": "nineties",
    "Nitin Mukesh": "nineties",
    "Abhijeet": "nineties",
    "Abhijeet Bhattacharya": "nineties",
    "Babul Supriyo": "nineties",
    "Sapna Mukherjee": "nineties",
    "Vinod Rathod": "nineties",
    "Sukhwinder Singh": "nineties",
    "Jatin-Lalit": "nineties",
    "Anand-Milind": "nineties",
    "Anu Malik": "nineties",
    "Hariharan": "nineties",
    "Suresh Wadkar": "nineties",
    "Lucky Ali": "nineties",
    "Sayeed Quadri": "nineties",
    "Aadesh Shrivastava": "nineties",
    "Roop Kumar Rathod": "nineties",
    "Labh Janjua": "nineties",
    "Bappi Lahiri": "nineties",
    # Pre-nineties classics (still treated as nineties because the engine
    # currently only has nineties as the oldest era bucket)
    "Lata Mangeshkar": "nineties",
    "Mohammed Rafi": "nineties",
    "Mohd. Rafi": "nineties",
    "Kishore Kumar": "nineties",
    "Mukesh": "nineties",
    "Asha Bhosle": "nineties",
    "R.D. Burman": "nineties",
    "RD Burman": "nineties",
    "Pankaj Udhas": "nineties",
    "Talat Mahmood": "nineties",
    "Shamshad Begum": "nineties",
    "Manna Dey": "nineties",
    "Hemant Kumar": "nineties",
    "Geeta Dutt": "nineties",
    "Suman Kalyanpur": "nineties",
    "Mahendra Kapoor": "nineties",
}
