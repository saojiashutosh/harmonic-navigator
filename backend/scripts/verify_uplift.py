"""Verify that goal=uplift on a melancholic-inferred user produces upbeat tracks."""
from collections import Counter

from django.core.cache import cache

from playlists.services import _build_candidate_pool, _score_track, _track_matches_language


def main():
    cache.clear()

    # Simulate the exact answers the user reported: drained / sad / drifting /
    # relaxing / alone / hindi / UPLIFT / late-night / 2010s.
    # Inferred mood for this set is "melancholic".
    tracks = _build_candidate_pool(
        mood_label="celebratory",          # what the new override resolves to
        secondary_mood="energized",
        social_setting="alone",
        music_preference=None,
        music_language="hindi",
        music_style=None,
        preferred_artist="",
        era_preference="era_2010s",
        limit=15,
    )

    print(f"candidate pool size: {len(tracks)}")
    primary_dist = Counter(t.primaryMood for t in tracks)
    print(f"primaryMood mix in pool: {dict(primary_dist)}")

    # Score the top 15
    scored = []
    for t in tracks:
        s = _score_track(
            track=t,
            mood_label="celebratory",
            secondary_mood="energized",
            mood_blend_ratio=0.85,
            type_weights={"song": 1.0, "instrumental": 0.0, "ambient": 0.0},
            music_preference=None,
            music_language='["hindi"]',
            music_style=None,
            playlist_goal="uplift",
            preferred_artist="",
            era_preference="era_2010s",
            time_of_day="late_night",
            feedback_map={},
            mood_tag_ids={},
        )
        scored.append((t, s))
    scored.sort(key=lambda x: x[1], reverse=True)

    print("\nTop 15 by score:")
    for t, s in scored[:15]:
        artist = t.artistId.name if t.artistId else "?"
        print(f"  {s:5.2f}  {t.primaryMood:12s}  {t.title[:45]:45s}  {artist[:20]:20s}  {t.releaseYear}")

    top_15_moods = Counter(t.primaryMood for t, _ in scored[:15])
    print(f"\nTop 15 mood distribution: {dict(top_15_moods)}")


if __name__ == "__main__":
    main()
