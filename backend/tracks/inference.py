from typing import Dict, Any
from .models import Track

# Ported/adapted from services.py MOOD_SIGNATURES
MOOD_MAPPING = {
    "celebratory": {"energy": 0.85, "valence": 0.8},
    "energized": {"energy": 0.8, "valence": 0.6},
    "calm": {"energy": 0.35, "valence": 0.5},
    "melancholic": {"energy": 0.3, "valence": 0.3},
    "anxious": {"energy": 0.6, "valence": 0.3},
    "focused": {"energy": 0.5, "valence": 0.5},
}

GENRE_MOOD_HINTS = {
    "lofi": "calm",
    "meditation": "calm",
    "ambient": "calm",
    "chill": "calm",
    "bollywood": "energized",
    "dance": "celebratory",
    "party": "celebratory",
    "sad": "melancholic",
    "ghazal": "calm",
    "classical": "focused",
    "rock": "energized",
    "pop": "energized",
    "indie": "focused",
}

class FeatureInferenceService:
    """
    Service to estimate missing audio features (energy, valence, tempo, etc.)
    based on song metadata and discovery context.
    """
    
    @staticmethod
    def infer_features(track_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Infer features for a track.
        context can contain: language, genre, query, region
        """
        genre = (context.get("genre") or "").lower()
        query = (context.get("query") or "").lower()
        
        # Determine primary mood hint
        mood_hint = "focused"
        for hint, mood in GENRE_MOOD_HINTS.items():
            if hint in genre or hint in query:
                mood_hint = mood
                break
        
        # Get base values from mapping
        base_values = MOOD_MAPPING.get(mood_hint, MOOD_MAPPING["focused"])
        
        # Estimate features
        inferred = {
            "energy": base_values["energy"],
            "valence": base_values["valence"],
            "acousticness": 0.5,
            "instrumentalness": 0.1,
            "loudness": -8.0,
            "tempoBpm": 120,
            "primaryMood": mood_hint,
        }
        
        # Refine based on context
        if "lofi" in query or "calm" in query:
            inferred["tempoBpm"] = 80
            inferred["loudness"] = -12.0
            inferred["acousticness"] = 0.8
            
        if "dance" in query or "techno" in query:
            inferred["tempoBpm"] = 128
            inferred["loudness"] = -6.0
            inferred["instrumentalness"] = 0.4
            
        return inferred

    @staticmethod
    def apply_inference(track: Track, context: Dict[str, Any] = None):
        """
        Safely applies inferred features to a Track instance if they are missing.
        """
        context = context or {
            "genre": track.genre or "",
            "language": track.language or "",
        }
        
        inferred = FeatureInferenceService.infer_features({}, context)
        
        fields_to_update = []
        
        if track.energy is None:
            track.energy = inferred["energy"]
            fields_to_update.append("energy")
            
        if track.valence is None:
            track.valence = inferred["valence"]
            fields_to_update.append("valence")
            
        if track.tempoBpm is None:
            track.tempoBpm = inferred["tempoBpm"]
            fields_to_update.append("tempoBpm")
            
        if track.primaryMood is None or track.primaryMood == "focused":
            track.primaryMood = inferred["primaryMood"]
            fields_to_update.append("primaryMood")
            
        if track.acousticness is None:
            track.acousticness = inferred["acousticness"]
            fields_to_update.append("acousticness")

        if fields_to_update:
            track.save(update_fields=fields_to_update)
