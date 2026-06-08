"""Smoke test for the in-house audio analysis engine.

Downloads a few deliberately contrasting songs from JioSaavn and runs them
through ``tracks.analysis.engine.analyze_audio_bytes``, printing every
extracted feature. This exercises the whole pipeline — audio_source -> dsp
-> extractors -> classifiers — with NO database involved.

Run inside the backend container:
    docker compose run --rm --no-deps web python scripts/test_audio_engine.py
"""
import os
import sys
import time
import traceback

# Make the backend project root importable when run as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tracks.analysis.audio_source import AudioAnalysisError, fetch_track_audio
from tracks.analysis.engine import analyze_audio_bytes

# Deliberately spread across moods / genres / regions so we can see the
# engine differentiate rather than return one flat answer.
SONGS = [
    {"title": "Tum Hi Ho", "artist": "Arijit Singh", "language": "hindi",
     "expect": "slow sad Bollywood ballad -> low energy, low valence"},
    {"title": "Lungi Dance", "artist": "Yo Yo Honey Singh", "language": "hindi",
     "expect": "high-energy dance track -> high energy, upbeat mood"},
    {"title": "Faded", "artist": "Alan Walker", "language": "english",
     "expect": "EDM -> high energy, electronic genre, US/UK region"},
    {"title": "Koi Hota Jisko Apna", "artist": "Kishore Kumar", "language": "hindi",
     "expect": "soft acoustic-leaning track -> low energy, acoustic"},
]


def _bar(value, width=20):
    """Tiny ASCII meter for a 0-1 value."""
    filled = int(round(max(0.0, min(1.0, value)) * width))
    return "#" * filled + "-" * (width - filled)


def run():
    passed, failed = 0, 0
    for i, song in enumerate(SONGS, 1):
        label = f"{song['title']} — {song['artist']}"
        print("\n" + "=" * 70)
        print(f"[{i}/{len(SONGS)}] {label}")
        print(f"    expectation: {song['expect']}")
        print("=" * 70)

        try:
            t0 = time.time()
            audio_bytes, url = fetch_track_audio(song["title"], song["artist"])
            dl = time.time() - t0
            print(f"  downloaded {len(audio_bytes)/1024:.0f} KB in {dl:.1f}s")

            t0 = time.time()
            f = analyze_audio_bytes(audio_bytes, metadata={"language": song["language"]})
            an = time.time() - t0
            print(f"  analysed in {an:.1f}s\n")

            print(f"  energy           {f['energy']:.2f}  {_bar(f['energy'])}")
            print(f"  valence          {f['valence']:.2f}  {_bar(f['valence'])}")
            print(f"  acousticness     {f['acousticness']:.2f}  {_bar(f['acousticness'])}")
            print(f"  instrumentalness {f['instrumentalness']:.2f}  {_bar(f['instrumentalness'])}")
            print(f"  tempo            {f['tempoBpm']} BPM")
            print(f"  loudness         {f['loudness']} dB")
            print(f"  key              {f['keySignature']}")
            print(f"  mood             {f['primaryMood']}  (conf {f['moodConfidence']:.2f})")
            print(f"  genre            {f['genre']}  (conf {f['genreConfidence']:.2f})")
            print(f"  region           {f['region']}  (conf {f['regionConfidence']:.2f})")
            print(f"  duration         {f['durationSec']}s")

            fv = f["featureVector"]
            print("\n  DSP internals:")
            print(f"    brightness={fv['brightness']:.2f} flatness={fv['spectral_flatness']:.2f} "
                  f"zcr={fv['zero_crossing_rate']:.2f}")
            print(f"    harmonic/percussive={fv['harmonic_ratio']:.2f}/{fv['percussive_ratio']:.2f} "
                  f"pulse_clarity={fv['pulse_clarity']:.2f} key_strength={fv['key_strength']:.2f}")
            passed += 1
        except AudioAnalysisError as exc:
            print(f"  SKIPPED — {exc}")
            failed += 1
        except Exception as exc:
            print(f"  FAILED — {exc}")
            traceback.print_exc()
            failed += 1

        time.sleep(1.5)  # be kind to JioSaavn

    print("\n" + "=" * 70)
    print(f"RESULT: {passed} analysed, {failed} failed/skipped")
    print("=" * 70)


if __name__ == "__main__":
    run()
