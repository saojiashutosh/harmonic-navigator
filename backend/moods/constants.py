# How each question answer nudges each mood score.
# Keys must match Question.key values in the DB.
# Values are dicts of {mood_label: weight} and can be negative.

# ---------------------------------------------------------------------------
# Category importance multipliers  (applied in inference.py)
# ---------------------------------------------------------------------------
CATEGORY_WEIGHTS = {
    "emotion":    1.60,   # Strongest mood signal
    "energy":     1.30,   # Maps directly to energy/valence
    "cognition":  1.10,   # Sharp vs scattered matters
    "activity":   1.00,   # Moderate signal
    "preference": 0.90,   # Influences track selection more than mood
    "context":    0.70,   # Weakest mood signal
}

# ---------------------------------------------------------------------------
# Cross-question synergy bonuses
# Each entry: (set of rawValue answers that must ALL be present, mood, bonus)
# ---------------------------------------------------------------------------
SYNERGY_BONUSES = [
    ({"sad", "drifting", "escape"},           "melancholic",  0.35),
    ({"happy", "charged", "party"},           "celebratory",  0.40),
    ({"calm", "relaxing", "sleep"},           "calm",         0.20),
    ({"sharp", "motivated", "focus"},         "focused",      0.30),
    ({"tense", "scattered", "working"},       "anxious",      0.25),
    ({"excited", "social", "party"},          "celebratory",  0.35),
    ({"drained", "sad", "relaxing"},          "melancholic",  0.30),
    ({"charged", "exercising", "uplift"},     "energized",    0.35),
    ({"calm", "drifting", "relax"},           "calm",         0.18),
    ({"happy", "exercising", "uplift"},       "energized",    0.30),
    ({"flat", "blank", "escape"},             "melancholic",  0.30),
    ({"sharp", "working", "focus"},           "focused",      0.28),
    ({"excited", "charged", "uplift"},        "energized",    0.32),
    ({"calm", "sleeping", "sleep"},           "calm",         0.25),
    ({"sleeping", "sleep", "drained"},        "calm",         0.35),
    ({"tense", "sleeping", "sleep"},          "calm",         0.30),
    ({"blank", "sleeping", "sleep"},          "calm",         0.28),
    ({"tense", "drained", "escape"},          "anxious",      0.25),
    ({"happy", "social", "lyrics"},           "celebratory",  0.25),
    ({"sad", "alone", "lyrics"},              "melancholic",  0.28),
    ({"motivated", "exercising", "party"},    "energized",    0.30),
]

QUESTION_DEFINITIONS = [
    {
        "key": "energy_level",
        "text": "How's your energy feeling right now?",
        "category": "energy",
        "inputType": "select",
        "order": 1,
        "options": [
            {"rawValue": "drained", "label": "Completely drained / exhausted"},
            {"rawValue": "low", "label": "Low — running on empty"},
            {"rawValue": "mid", "label": "Somewhere in the middle"},
            {"rawValue": "good", "label": "Pretty good, feeling alive"},
            {"rawValue": "charged", "label": "Fully charged and pumped"},
        ],
    },
    {
        "key": "emotional_tone",
        "text": "How are you feeling emotionally right now?",
        "category": "emotion",
        "inputType": "select",
        "order": 2,
        "options": [
            {"rawValue": "happy", "label": "Happy & cheerful"},
            {"rawValue": "calm", "label": "Calm & at peace"},
            {"rawValue": "sad", "label": "Sad or down"},
            {"rawValue": "tense", "label": "Stressed or anxious"},
            {"rawValue": "flat", "label": "Numb or indifferent"},
            {"rawValue": "excited", "label": "Excited & thrilled"},
        ],
    },
    {
        "key": "mental_state",
        "text": "What is your headspace like right now?",
        "category": "cognition",
        "inputType": "select",
        "order": 3,
        "options": [
            {"rawValue": "sharp", "label": "Sharp — ready to focus"},
            {"rawValue": "scattered", "label": "Scattered — hard to concentrate"},
            {"rawValue": "drifting", "label": "Drifting — lost in thought"},
            {"rawValue": "motivated", "label": "Switched on and motivated"},
            {"rawValue": "blank", "label": "Blank — not thinking much"},
        ],
    },
    {
        "key": "activity",
        "text": "What are you currently doing?",
        "category": "activity",
        "inputType": "select",
        "order": 4,
        "options": [
            {"rawValue": "working", "label": "Working or studying"},
            {"rawValue": "exercising", "label": "Exercising or moving"},
            {"rawValue": "relaxing", "label": "Relaxing or chilling"},
            {"rawValue": "commuting", "label": "Commuting or travelling"},
            {"rawValue": "social", "label": "Socialising or celebrating"},
            {"rawValue": "sleeping", "label": "Winding down or sleeping"},
        ],
    },
    {
        "key": "social_setting",
        "text": "Who are you with right now?",
        "category": "context",
        "inputType": "select",
        "order": 5,
        "options": [
            {"rawValue": "alone", "label": "Just me, alone"},
            {"rawValue": "others", "label": "With friends or family"},
            {"rawValue": "kids", "label": "With kids"},
            {"rawValue": "meeting", "label": "In a meeting or workspace"},
        ],
    },
    {
        "key": "music_language",
        "text": "Which language songs do you prefer?",
        "category": "preference",
        "inputType": "select",
        "order": 6,
        "options": [
            {"rawValue": "hindi", "label": "Hindi"},
            {"rawValue": "marathi", "label": "Marathi"},
            {"rawValue": "no_preference", "label": "No preference"},
        ],
    },
    {
        "key": "playlist_goal",
        "text": "What should this playlist do for you?",
        "category": "preference",
        "inputType": "select",
        "order": 7,
        "options": [
            {"rawValue": "focus", "label": "Help me focus and concentrate"},
            {"rawValue": "relax", "label": "Help me relax and slow down"},
            {"rawValue": "uplift", "label": "Lift my mood"},
            {"rawValue": "escape", "label": "Help me escape and drift"},
            {"rawValue": "party", "label": "Get the party going"},
            {"rawValue": "sleep", "label": "Help me rest or sleep"},
        ],
    },
    {
        "key": "preferred_artist",
        "text": "Any artist you want to hear? Leave blank if not.",
        "category": "preference",
        "inputType": "text",
        "order": 8,
        "options": [],
    },
    {
        "key": "time_of_day",
        "text": "What time of day is it for you?",
        "category": "context",
        "inputType": "select",
        "order": 9,
        "options": [
            {"rawValue": "morning", "label": "Morning — fresh start"},
            {"rawValue": "afternoon", "label": "Afternoon — mid-day groove"},
            {"rawValue": "evening", "label": "Evening — winding down"},
            {"rawValue": "late_night", "label": "Late night — quiet hours"},
        ],
    },
    {
        "key": "music_era",
        "text": "From which era do you want your songs?",
        "category": "preference",
        "inputType": "select",
        "order": 10,
        "options": [
            {"rawValue": "latest", "label": "Latest — 2024 & newer"},
            {"rawValue": "recent", "label": "Recent — 2020 to 2023"},
            {"rawValue": "era_2010s", "label": "2010s decade"},
            {"rawValue": "era_2000s", "label": "2000s nostalgia"},
            {"rawValue": "nineties", "label": "90s — 1996 to 1999"},
        ],
    },
]

# ---------------------------------------------------------------------------
# QUESTION_WEIGHTS — mood nudges per (question_key + rawValue) combo
# ---------------------------------------------------------------------------
QUESTION_WEIGHTS = {
    # ── energy_level ──────────────────────────────────────────────────────
    "energy_level_drained": {
        "calm": 0.45,
        "melancholic": 0.55,
        "anxious": 0.15,
        "focused": -0.20,
        "energized": -0.50,
        "celebratory": -0.45,
    },
    "energy_level_low": {
        "calm": 0.30,
        "melancholic": 0.35,
        "anxious": 0.10,
        "focused": -0.10,
        "energized": -0.30,
        "celebratory": -0.25,
    },
    "energy_level_mid": {
        "focused": 0.35,
        "calm": 0.15,
        "melancholic": 0.05,
        "anxious": 0.00,
        "energized": 0.05,
        "celebratory": 0.00,
    },
    "energy_level_good": {
        "energized": 0.35,
        "focused": 0.25,
        "celebratory": 0.15,
        "calm": -0.10,
        "melancholic": -0.15,
        "anxious": 0.05,
    },
    "energy_level_charged": {
        "energized": 0.55,
        "celebratory": 0.35,
        "focused": 0.15,
        "calm": -0.25,
        "melancholic": -0.30,
        "anxious": 0.10,
    },
    # ── emotional_tone ────────────────────────────────────────────────────
    "emotional_tone_happy": {
        "energized": 0.35,
        "celebratory": 0.40,
        "melancholic": -0.40,
        "anxious": -0.20,
        "calm": 0.10,
        "focused": 0.05,
    },
    "emotional_tone_calm": {
        "calm": 0.55,
        "focused": 0.25,
        "melancholic": 0.10,
        "energized": -0.30,
        "celebratory": -0.35,
        "anxious": -0.30,
    },
    "emotional_tone_sad": {
        "melancholic": 0.60,
        "calm": 0.15,
        "anxious": 0.15,
        "focused": -0.15,
        "energized": -0.45,
        "celebratory": -0.50,
    },
    "emotional_tone_tense": {
        "anxious": 0.65,
        "melancholic": 0.10,
        "energized": 0.10,
        "calm": -0.40,
        "focused": -0.20,
        "celebratory": -0.35,
    },
    "emotional_tone_flat": {
        "melancholic": 0.55,
        "calm": 0.15,
        "focused": -0.10,
        "energized": -0.40,
        "celebratory": -0.45,
        "anxious": 0.10,
    },
    "emotional_tone_excited": {
        "celebratory": 0.55,
        "energized": 0.35,
        "focused": -0.10,
        "calm": -0.35,
        "melancholic": -0.45,
        "anxious": -0.15,
    },
    # ── mental_state ──────────────────────────────────────────────────────
    "mental_state_sharp": {
        "focused": 0.60,
        "energized": 0.15,
        "calm": 0.10,
        "anxious": -0.25,
        "melancholic": -0.20,
        "celebratory": 0.05,
    },
    "mental_state_scattered": {
        "anxious": 0.55,
        "melancholic": 0.15,
        "focused": -0.35,
        "calm": -0.25,
        "energized": 0.05,
        "celebratory": -0.20,
    },
    "mental_state_drifting": {
        "melancholic": 0.50,
        "calm": 0.18,
        "focused": -0.20,
        "energized": -0.30,
        "celebratory": -0.35,
        "anxious": 0.05,
    },
    "mental_state_motivated": {
        "energized": 0.45,
        "celebratory": 0.30,
        "focused": 0.15,
        "melancholic": -0.40,
        "calm": -0.25,
        "anxious": -0.10,
    },
    "mental_state_blank": {
        "melancholic": 0.40,
        "calm": 0.18,
        "focused": -0.15,
        "energized": -0.35,
        "celebratory": -0.40,
        "anxious": 0.05,
    },
    # ── activity ──────────────────────────────────────────────────────────
    "activity_working": {
        "focused": 0.60,
        "calm": 0.15,
        "anxious": 0.10,
        "energized": -0.15,
        "celebratory": -0.35,
        "melancholic": 0.00,
    },
    "activity_exercising": {
        "energized": 0.60,
        "celebratory": 0.20,
        "focused": 0.10,
        "calm": -0.30,
        "melancholic": -0.35,
        "anxious": -0.10,
    },
    "activity_relaxing": {
        "calm": 0.55,
        "melancholic": 0.20,
        "focused": -0.15,
        "energized": -0.40,
        "celebratory": -0.30,
        "anxious": -0.20,
    },
    "activity_commuting": {
        "focused": 0.45,
        "melancholic": 0.20,
        "energized": 0.15,
        "calm": 0.08,
        "anxious": 0.05,
        "celebratory": -0.10,
    },
    "activity_social": {
        "celebratory": 0.55,
        "energized": 0.30,
        "focused": -0.25,
        "calm": -0.15,
        "melancholic": -0.35,
        "anxious": -0.10,
    },
    "activity_sleeping": {
        "calm": 0.65,
        "melancholic": 0.15,
        "focused": -0.20,
        "energized": -0.50,
        "celebratory": -0.55,
        "anxious": -0.30,
    },
    # ── social_setting ────────────────────────────────────────────────────
    "social_setting_alone": {
        "focused": 0.10,
        "melancholic": 0.10,
        "calm": 0.05,
        "celebratory": -0.05,
        "energized": 0.00,
        "anxious": 0.00,
    },
    "social_setting_others": {
        "celebratory": 0.20,
        "energized": 0.10,
        "focused": -0.10,
        "melancholic": -0.15,
        "calm": -0.05,
        "anxious": 0.00,
    },
    "social_setting_kids": {
        "calm": 0.20,
        "celebratory": 0.10,
        "anxious": -0.10,
        "melancholic": -0.10,
        "focused": -0.05,
        "energized": 0.05,
    },
    "social_setting_meeting": {
        "focused": 0.30,
        "calm": 0.15,
        "anxious": 0.10,
        "celebratory": -0.20,
        "energized": -0.10,
        "melancholic": -0.05,
    },
    # ── music_language ────────────────────────────────────────────────────
    "music_language_no_preference": {
        "energized": 0.00,
        "celebratory": 0.00,
        "focused": 0.00,
        "calm": 0.00,
        "melancholic": 0.00,
        "anxious": 0.00,
    },
    "music_language_hindi": {
        "celebratory": 0.12,
        "energized": 0.10,
        "melancholic": 0.05,
        "calm": -0.05,
        "focused": -0.05,
        "anxious": -0.03,
    },
    "music_language_english": {
        "energized": 0.08,
        "celebratory": 0.06,
        "focused": 0.04,
        "calm": -0.02,
        "melancholic": -0.02,
        "anxious": -0.02,
    },
    "music_language_marathi": {
        "calm": 0.10,
        "melancholic": 0.08,
        "celebratory": 0.05,
        "energized": 0.00,
        "focused": -0.02,
        "anxious": -0.03,
    },
    # ── music_style ───────────────────────────────────────────────────────
    "music_style_no_preference": {
        "energized": 0.00,
        "celebratory": 0.00,
        "focused": 0.00,
        "calm": 0.00,
        "melancholic": 0.00,
        "anxious": 0.00,
    },
    "music_style_bollywood": {
        "celebratory": 0.14,
        "energized": 0.12,
        "melancholic": 0.05,
        "calm": -0.05,
        "focused": -0.08,
        "anxious": -0.05,
    },
    "music_style_hollywood": {
        "energized": 0.10,
        "celebratory": 0.08,
        "focused": 0.04,
        "calm": -0.03,
        "melancholic": -0.03,
        "anxious": -0.03,
    },
    "music_style_pop": {
        "energized": 0.12,
        "celebratory": 0.10,
        "focused": -0.05,
        "calm": -0.08,
        "melancholic": -0.05,
        "anxious": -0.05,
    },
    "music_style_indie": {
        "melancholic": 0.12,
        "calm": 0.10,
        "focused": 0.05,
        "energized": -0.05,
        "celebratory": -0.08,
        "anxious": 0.00,
    },
    "music_style_classical": {
        "calm": 0.18,
        "focused": 0.14,
        "melancholic": 0.08,
        "energized": -0.10,
        "celebratory": -0.12,
        "anxious": -0.10,
    },
    "music_style_raga": {
        "calm": 0.20,
        "focused": 0.12,
        "melancholic": 0.10,
        "energized": -0.12,
        "celebratory": -0.14,
        "anxious": -0.08,
    },
    "music_style_lofi": {
        "calm": 0.20,
        "focused": 0.15,
        "melancholic": 0.10,
        "energized": -0.15,
        "celebratory": -0.18,
        "anxious": -0.08,
    },
    "music_style_devotional": {
        "calm": 0.25,
        "melancholic": 0.08,
        "focused": 0.05,
        "energized": -0.12,
        "celebratory": -0.10,
        "anxious": -0.15,
    },
    "music_style_marathi": {
        "calm": 0.18,
        "melancholic": 0.10,
        "celebratory": 0.08,
        "energized": 0.00,
        "focused": -0.02,
        "anxious": -0.05,
    },
    "music_style_instrumental": {
        "focused": 0.20,
        "calm": 0.18,
        "melancholic": 0.08,
        "energized": -0.10,
        "celebratory": -0.14,
        "anxious": -0.08,
    },
    # ── playlist_goal ─────────────────────────────────────────────────────
    "playlist_goal_focus": {
        "focused": 0.75,
        "calm": 0.15,
        "energized": 0.05,
        "anxious": -0.20,
        "melancholic": -0.10,
        "celebratory": -0.20,
    },
    "playlist_goal_relax": {
        "calm": 0.60,
        "melancholic": 0.22,
        "focused": 0.05,
        "energized": -0.30,
        "celebratory": -0.30,
        "anxious": -0.25,
    },
    "playlist_goal_uplift": {
        "energized": 0.55,
        "celebratory": 0.50,
        "calm": 0.05,
        "focused": 0.08,
        "melancholic": -0.30,
        "anxious": -0.10,
    },
    "playlist_goal_escape": {
        "melancholic": 0.65,
        "calm": 0.15,
        "focused": -0.05,
        "energized": -0.15,
        "celebratory": -0.18,
        "anxious": -0.05,
    },
    "playlist_goal_party": {
        "celebratory": 0.75,
        "energized": 0.55,
        "focused": -0.15,
        "calm": -0.30,
        "melancholic": -0.40,
        "anxious": -0.10,
    },
    "playlist_goal_sleep": {
        "calm": 0.90,
        "melancholic": 0.10,
        "focused": -0.25,
        "energized": -0.65,
        "celebratory": -0.65,
        "anxious": -0.50,
    },
    # ── time_of_day (NEW question) ────────────────────────────────────────
    "time_of_day_morning": {
        "energized": 0.25,
        "focused": 0.20,
        "celebratory": 0.05,
        "calm": -0.05,
        "melancholic": -0.15,
        "anxious": -0.08,
    },
    "time_of_day_afternoon": {
        "focused": 0.15,
        "energized": 0.10,
        "calm": 0.05,
        "celebratory": 0.00,
        "melancholic": -0.05,
        "anxious": 0.00,
    },
    "time_of_day_evening": {
        "melancholic": 0.20,
        "calm": 0.10,
        "focused": -0.05,
        "energized": -0.10,
        "celebratory": 0.05,
        "anxious": -0.05,
    },
    "time_of_day_late_night": {
        "calm": 0.30,
        "melancholic": 0.20,
        "focused": -0.15,
        "energized": -0.35,
        "celebratory": -0.30,
        "anxious": -0.05,
    },
    # ── music_era ─────────────────────────────────────────────────────────
    "music_era_latest": {
        "energized": 0.10, "celebratory": 0.08, "focused": 0.04,
        "calm": -0.04, "melancholic": -0.06, "anxious": -0.02,
    },
    "music_era_recent": {
        "energized": 0.08, "celebratory": 0.06, "focused": 0.04,
        "calm": 0.00, "melancholic": -0.04, "anxious": -0.02,
    },
    "music_era_era_2010s": {
        "energized": 0.04, "celebratory": 0.04, "focused": 0.04,
        "calm": 0.04, "melancholic": 0.04, "anxious": 0.00,
    },
    "music_era_era_2000s": {
        "calm": 0.06, "melancholic": 0.08, "celebratory": 0.05,
        "focused": 0.03, "energized": -0.03, "anxious": -0.02,
    },
    "music_era_nineties": {
        "melancholic": 0.12, "calm": 0.10, "celebratory": 0.06,
        "focused": -0.03, "energized": -0.06, "anxious": -0.04,
    },
    "music_era_no_preference": {
        "energized": 0.00, "celebratory": 0.00, "focused": 0.00,
        "calm": 0.00, "melancholic": 0.00, "anxious": 0.00,
    },
}

# ---------------------------------------------------------------------------
# Per-option intensity values — all 1.0.
# QUESTION_WEIGHTS already encode the correct magnitude for each answer choice
# (e.g. energy_level_drained vs energy_level_charged have separate weight dicts).
# Multiplying by a second intensity factor was dampening emotional signals like
# "sad" (0.30) and "flat" (0.20) to 3–5× less than positive states — the root
# cause of consistently low confidence scores.
# ---------------------------------------------------------------------------
OPTION_WEIGHTS = {
    # energy_level
    "drained":    1.00,
    "low":        1.00,
    "mid":        1.00,
    "good":       1.00,
    "charged":    1.00,
    # emotional_tone
    "happy":      1.00,
    "calm":       1.00,
    "sad":        1.00,
    "tense":      1.00,
    "flat":       1.00,
    "excited":    1.00,
    # mental_state
    "sharp":      1.00,
    "scattered":  1.00,
    "drifting":   1.00,
    "motivated":  1.00,
    "blank":      1.00,
    # activity
    "working":    1.00,
    "exercising": 1.00,
    "relaxing":   1.00,
    "commuting":  1.00,
    "social":     1.00,
    "sleeping":   1.00,
    # social_setting
    "alone":      1.00,
    "others":     1.00,
    "kids":       1.00,
    "meeting":    1.00,
    # music_language
    "no_preference":  1.00,
    "hindi":          1.00,
    "english":        1.00,
    "marathi":        1.00,
    # music_style
    "bollywood":      1.00,
    "hollywood":      1.00,
    "pop":            1.00,
    "indie":          1.00,
    "classical":      1.00,
    "raga":           1.00,
    "lofi":           1.00,
    "devotional":     1.00,
    # playlist_goal
    "focus":          1.00,
    "relax":          1.00,
    "uplift":         1.00,
    "escape":         1.00,
    "party":          1.00,
    "sleep":          1.00,
    # time_of_day
    "morning":        1.00,
    "afternoon":      1.00,
    "evening":        1.00,
    "late_night":     1.00,
    # music_era
    "latest":         1.00,
    "recent":         1.00,
    "era_2010s":      1.00,
    "era_2000s":      1.00,
    "nineties":       1.00,
}

MUSIC_PREFERENCE_OVERRIDES = {
    "lyrics": {"song": 0.80, "instrumental": 0.15, "ambient": 0.05},
    "no_lyrics": {"song": 0.05, "instrumental": 0.75, "ambient": 0.20},
    "background": {"song": 0.05, "instrumental": 0.25, "ambient": 0.70},
    "surprise": None,
}
