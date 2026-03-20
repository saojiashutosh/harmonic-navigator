# How each question answer nudges each mood score.
# Keys must match Question.key values in the DB.
# Values are dicts of {mood_label: weight} and can be negative.

QUESTION_WEIGHTS = {
    "energy_level": {
        "energized": 0.45,
        "focused": 0.20,
        "celebratory": 0.20,
        "melancholic": -0.25,
        "anxious": 0.10,
        "calm": -0.20,
    },
    "emotion_happy": {
        "energized": 0.30,
        "celebratory": 0.45,
        "focused": 0.05,
        "melancholic": -0.35,
        "anxious": -0.10,
        "calm": 0.10,
    },
    "emotion_sad": {
        "melancholic": 0.55,
        "anxious": 0.20,
        "calm": 0.10,
        "focused": -0.10,
        "energized": -0.40,
        "celebratory": -0.45,
    },
    "emotion_anxious": {
        "anxious": 0.60,
        "melancholic": 0.15,
        "focused": -0.10,
        "energized": -0.15,
        "calm": -0.35,
        "celebratory": -0.40,
    },
    "activity_working": {
        "focused": 0.55,
        "calm": 0.15,
        "energized": -0.10,
        "celebratory": -0.30,
        "anxious": 0.10,
        "melancholic": -0.05,
    },
    "activity_exercising": {
        "energized": 0.55,
        "celebratory": 0.20,
        "focused": 0.10,
        "calm": -0.25,
        "melancholic": -0.30,
        "anxious": -0.10,
    },
    "activity_winding_down": {
        "calm": 0.55,
        "melancholic": 0.15,
        "focused": -0.10,
        "energized": -0.35,
        "celebratory": -0.25,
        "anxious": -0.15,
    },
    "activity_social": {
        "celebratory": 0.50,
        "energized": 0.25,
        "calm": -0.10,
        "melancholic": -0.30,
        "anxious": -0.10,
        "focused": -0.20,
    },
}

# Maps select-type option strings to a normalized float for storage in Answer.value.
OPTION_WEIGHTS = {
    "very_happy": 1.0,
    "happy": 0.75,
    "neutral": 0.50,
    "sad": 0.25,
    "very_sad": 0.0,
    "working": 1.0,
    "exercising": 1.0,
    "winding_down": 1.0,
    "social": 1.0,
    "commuting": 0.5,
    "other": 0.5,
}
