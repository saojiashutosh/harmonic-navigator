"""One-off smoke test for the era recommendation engine fix."""
from django.core.cache import cache

from playlists.services import _era_query, _inferred_artist_era, _track_matches_era
from tracks.models import Track


def main():
    cache.clear()
    print("cache cleared")

    for era in ("nineties", "era_2000s", "era_2010s", "recent", "latest"):
        qs = Track.objects.filter(_era_query(era), isActive=True)
        print(f"  {era:11s} candidate pool: {qs.count():4d} tracks")

    print()
    sample = (
        Track.objects.select_related("artistId")
        .filter(artistId__name="Kumar Sanu", releaseYear__isnull=True)
        .first()
    )
    if sample:
        print(f"sample NULL-year Kumar Sanu track: {sample.title!r}")
        print(f"  inferred era: {_inferred_artist_era(sample)}")
        print(f"  matches nineties: {_track_matches_era(sample, 'nineties')}")
        print(f"  matches era_2010s: {_track_matches_era(sample, 'era_2010s')}")

    print()
    pre_1996 = Track.objects.filter(releaseYear__lt=1996, releaseYear__gte=1980).count()
    print(f"pre-1996 (1980-1995) tracks now reachable: {pre_1996}")


if __name__ == "__main__":
    main()
