DEFAULT_PLAYLIST_SIZE = 20

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
