#!/usr/bin/env python3
"""
Fetch release years for Spotify tracks using the official Spotify API (spotipy).
Run this LOCALLY (outside Docker) to use the local machine's IP / rate limit bucket.

Usage:
    python fetch_release_years.py pending_ids.json release_years.json
"""
from __future__ import annotations

import json
import os
import sys
import time


def build_client():
    from spotipy import Spotify
    from spotipy.oauth2 import SpotifyClientCredentials

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET env vars.")
    return Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
        ),
        requests_timeout=10,
        retries=0,  # no auto-retry — we handle errors manually
    )


def fetch_year(client, track_id: str) -> int | None:
    item = client.track(track_id)
    if not item:
        return None
    album = item.get("album") or {}
    release_date = album.get("release_date") or ""
    if release_date:
        try:
            return int(str(release_date)[:4])
        except (ValueError, TypeError):
            pass
    return None


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python fetch_release_years.py pending_ids.json release_years.json")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(input_file, encoding="utf-8-sig") as f:
        ids: list[str] = json.load(f)

    print(f"Loaded {len(ids)} track IDs.")

    # Load existing results to resume if interrupted
    try:
        with open(output_file, encoding="utf-8") as f:
            mapping: dict = json.load(f)
    except FileNotFoundError:
        mapping = {}

    already_done = sum(1 for v in mapping.values() if v is not None)
    remaining = [tid for tid in ids if tid not in mapping]
    print(f"Already fetched: {len(mapping)} ({already_done} with year). Remaining: {len(remaining)}")

    try:
        client = build_client()
        print("Spotify client ready.")
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    fetched = 0
    errors = 0

    for i, track_id in enumerate(remaining):
        try:
            year = fetch_year(client, track_id)
            mapping[track_id] = year
            fetched += 1
            if fetched % 50 == 0:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(mapping, f)
                print(f"  Progress: {fetched} fetched, {errors} errors...")
        except Exception as exc:
            errors += 1
            mapping[track_id] = None
            err_str = str(exc)
            if "429" in err_str or "rate" in err_str.lower():
                print(f"  Rate limited at {i}! Saving progress and stopping.")
                break
            if errors <= 10:
                print(f"  Error {track_id}: {exc}")

        time.sleep(0.15)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(mapping, f)

    years_found = sum(1 for v in mapping.values() if v is not None)
    print(f"\nDone. Total={len(mapping)}  Years found={years_found}  Errors={errors}")
    print(f"Output saved to: {output_file}")


if __name__ == "__main__":
    main()
