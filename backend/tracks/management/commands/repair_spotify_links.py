from __future__ import annotations

from difflib import SequenceMatcher

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tracks.excel_storage import export_tracks_to_excel
from tracks.models import Track
from tracks.services import (
    _build_key_signature,
    _round_positive,
    derive_is_instrumental,
    derive_primary_mood,
    derive_track_type,
)
from tracks.spotify_client import SpotifyConfigurationError, SpotifyImportError, get_track, search_tracks
from tracks.spotify_scraper import SpotifyScraper
from tracks.inference import FeatureInferenceService


class Command(BaseCommand):
    help = "Repair missing or incorrect Spotify IDs/URLs for existing tracks."

    def add_arguments(self, parser):
        parser.add_argument("--market", default=None, help="Spotify market code, e.g. IN or US.")
        parser.add_argument("--limit", type=int, default=None, help="Optional max number of tracks to inspect.")
        parser.add_argument(
            "--only-broken",
            action="store_true",
            help="Only process tracks with missing spotifyId or missing externalUrl.",
        )
        parser.add_argument("--sleep", type=float, default=0, help="Sleep duration between tracks in seconds.")
        parser.add_argument("--local-dataset", default=None, help="Path to a local CSV dataset (e.g. spotify_dataset.csv) for lookups.")
        parser.add_argument("--local-only", action="store_true", help="Only perform local lookups, no API calls.")
        parser.add_argument("--web-lookup", action="store_true", help="Perform a web search if API search fails.")
        parser.add_argument("--use-scraper", action="store_true", help="Use web scraper if API search fails or is blocked.")

    def handle(self, *args, **options):
        queryset = Track.objects.select_related("artistId").order_by("createdAt", "id")
        if options["only_broken"]:
            queryset = queryset.filter(spotifyId__isnull=True) | queryset.filter(spotifyId="") | queryset.filter(externalUrl__isnull=True) | queryset.filter(externalUrl="")
        if options["limit"]:
            queryset = queryset[: options["limit"]]

        total_count = queryset.count()
        repaired = 0
        skipped = 0
        failed = 0
        processed = 0

        self.stdout.write(f"Starting repair for {total_count} tracks...")

        self.local_mapping = {}
        self.do_web_lookup = options["web_lookup"]
        self.local_only = options["local_only"]
        self.use_scraper = options["use_scraper"]
        self.scraper = SpotifyScraper()
        if options["local_dataset"]:
            self.stdout.write(f"Loading local dataset from {options['local_dataset']}...")
            self._load_local_dataset(options["local_dataset"])

        import time
        for track in queryset:
            processed += 1
            if processed % 100 == 0:
                self.stdout.write(f"Processed {processed}/{total_count}...")
            try:
                changed = self._repair_track(track, market=options["market"])
            except (SpotifyConfigurationError, SpotifyImportError) as exc:
                failed += 1
                self.stderr.write(f"Failed {track.title}: {exc}")
                continue
            except Exception as exc:  # defensive batch processing
                failed += 1
                self.stderr.write(f"Unexpected failure for {track.title}: {exc}")
                continue

            if changed:
                repaired += 1
                self.stdout.write(f"Updated {track.title} -> {track.externalUrl or 'no external URL'}")
            else:
                skipped += 1

            if options["sleep"] > 0:
                time.sleep(options["sleep"])

        export_tracks_to_excel()
        self.stdout.write(
            self.style.SUCCESS(
                f"Spotify link repair finished. Updated={repaired} skipped={skipped} failed={failed}"
            )
        )

    def _repair_track(self, track: Track, *, market: str | None) -> bool:
        payload = None

        if payload is None:
            # Fallback 1: Local Dataset (Fast & Free)
            payload = self._search_local_dataset(track)

        if self.local_only:
            if payload is None:
                return False
            return self._apply_payload(track, payload)

        if payload is None and track.spotifyId:
            try:
                payload = get_track(track.spotifyId, market=market)
            except SpotifyImportError:
                payload = None
            
        if payload is None:
            # Fallback 2: API Search
            payload = self._search_best_match(track, market=market)
            
        if payload is None and (self.do_web_lookup or self.use_scraper):
            # Fallback 3: Web Lookup / Scraping
            payload = self._search_web_lookup(track)

        if payload:
            # Ensure all Track model fields are satisfied using inference
            # We convert payload to a temp Track to apply inference logic
            self._apply_payload(track, payload)
            FeatureInferenceService.apply_inference(track)
            return True

        return False

    def _search_best_match(self, track: Track, *, market: str | None) -> dict | None:
        artist_name = getattr(track.artistId, "name", "") or ""
        queries = [
            f'track:"{track.title}" artist:"{artist_name}"',
            f"{track.title} {artist_name}".strip(),
            str(track.title or "").strip(),
        ]

        candidates = []
        seen_ids = set()
        for query in queries:
            if not query:
                continue
            for payload in search_tracks(query=query, limit=5, market=market):
                spotify_id = payload.get("spotify_id")
                if not spotify_id or spotify_id in seen_ids:
                    continue
                seen_ids.add(spotify_id)
                candidates.append(payload)

        if not candidates:
            return None

        best_payload = None
        best_score = 0.0
        for payload in candidates:
            score = self._match_score(track, payload)
            if score > best_score:
                best_score = score
                best_payload = payload

        return best_payload if best_score >= 0.72 else None

    def _match_score(self, track: Track, payload: dict) -> float:
        artist_name = getattr(track.artistId, "name", "") or ""
        payload_artist = (payload.get("artist") or {}).get("name") or ""

        title_score = self._similarity(track.title or "", payload.get("title") or "")
        artist_score = self._similarity(artist_name, payload_artist)

        score = title_score * 0.65 + artist_score * 0.35
        if track.durationMs and payload.get("duration_ms"):
            delta = abs(int(track.durationMs) - int(payload["duration_ms"]))
            if delta <= 4000:
                score += 0.08
            elif delta >= 20000:
                score -= 0.15
        return score

    def _apply_payload(self, track: Track, payload: dict) -> bool:
        artist_payload = payload.get("artist") or {}
        audio_features = payload.get("audio_features") or {}
        changed = False

        with transaction.atomic():
            artist = track.artistId
            payload_artist_name = artist_payload.get("name")
            payload_artist_id = artist_payload.get("spotify_id")
            if artist and payload_artist_name and artist.name != payload_artist_name:
                artist.name = payload_artist_name
                changed = True
            if artist and payload_artist_id and artist.spotifyId != payload_artist_id:
                artist.spotifyId = payload_artist_id
                changed = True
            if changed and artist:
                artist.save(update_fields=["name", "spotifyId"])

            new_external_url = payload.get("external_url") or _canonical_track_url(payload.get("spotify_id"))
            field_updates = {
                "spotifyId": payload.get("spotify_id") or track.spotifyId,
                "title": payload.get("title") or track.title,
                "previewUrl": payload.get("preview_url"),
                "externalUrl": new_external_url,
                "durationMs": payload.get("duration_ms") or track.durationMs,
                "isExplicit": payload.get("is_explicit", track.isExplicit),
            }

            if audio_features:
                field_updates.update(
                    {
                        "tempoBpm": _round_positive(audio_features.get("tempo")),
                        "keySignature": _build_key_signature(audio_features),
                        "energy": audio_features.get("energy"),
                        "valence": audio_features.get("valence"),
                        "acousticness": audio_features.get("acousticness"),
                        "instrumentalness": audio_features.get("instrumentalness"),
                        "loudness": audio_features.get("loudness"),
                        "isInstrumental": derive_is_instrumental(audio_features),
                        "type": derive_track_type(audio_features),
                        "primaryMood": track.primaryMood or derive_primary_mood(audio_features),
                    }
                )

            changed_fields = []
            for field_name, value in field_updates.items():
                if value is None:
                    continue
                if getattr(track, field_name) != value:
                    setattr(track, field_name, value)
                    changed = True
                    changed_fields.append(field_name)

            if changed_fields:
                track.save(update_fields=changed_fields)

        return changed

    def _similarity(self, left: str, right: str) -> float:
        return SequenceMatcher(None, (left or "").strip().lower(), (right or "").strip().lower()).ratio()

    def _load_local_dataset(self, path: str):
        import csv
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    title = (row.get("track_name") or "").strip().lower()
                    artist = (row.get("artists") or "").split(";")[0].strip().lower()
                    if title and artist:
                        if title not in self.local_mapping:
                            self.local_mapping[title] = {}
                        self.local_mapping[title][artist] = row.get("track_id")
        except Exception as e:
            self.stderr.write(f"Failed to load local dataset: {e}")

    def _search_local_dataset(self, track: Track) -> dict | None:
        title = (track.title or "").strip().lower()
        artist_name = getattr(track.artistId, "name", "") or ""
        artist_name = artist_name.strip().lower()
        
        if title in self.local_mapping:
            # Try exact artist match
            if artist_name in self.local_mapping[title]:
                spotify_id = self.local_mapping[title][artist_name]
                return {"spotify_id": spotify_id, "title": track.title}
            
            # Try fuzzy artist match within the same title
            for local_artist, spotify_id in self.local_mapping[title].items():
                if self._similarity(artist_name, local_artist) > 0.8:
                    return {"spotify_id": spotify_id, "title": track.title}
        return None

    def _search_web_lookup(self, track: Track) -> dict | None:
        import requests
        import re
        from urllib.parse import quote_plus
        
        artist_name = getattr(track.artistId, "name", "") or ""
        query = f'site:open.spotify.com/track "{track.title}" {artist_name}'
        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                # Find track IDs like [A-Za-z0-9]{22}
                matches = re.findall(r"open\.spotify\.com/track/([A-Za-z0-9]{22})", resp.text)
                if matches:
                    spotify_id = matches[0]
                    
                    # Try API first unless suppressed
                    if not self.local_only:
                        try:
                            return get_track(spotify_id)
                        except Exception:
                            pass
                    
                    # Fallback to scraper
                    if self.use_scraper:
                        return self.scraper.scrape_track(spotify_id)
                    
        except Exception as e:
            self.stderr.write(f"Web lookup failed for {track.title}: {e}")
        return None


def _canonical_track_url(spotify_id: str | None) -> str | None:
    if not spotify_id:
        return None
    return f"https://open.spotify.com/track/{spotify_id}"
