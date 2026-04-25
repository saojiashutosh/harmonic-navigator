from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tracks.models import Artist, Track
from helpers.excel_storage import sync_track_to_excel
from helpers.spotify_scraper import SpotifyScraper, extract_track_id_from_url
from helpers.track_inference import FeatureInferenceService

class Command(BaseCommand):
    help = "Import Spotify tracks from a list of URLs using web scraping and feature inference."

    def add_arguments(self, parser):
        parser.add_argument("urls", nargs="+", help="One or more Spotify track URLs.")
        parser.add_argument("--language", default=None, help="Language for the imported tracks.")
        parser.add_argument("--genre", default=None, help="Genre for the imported tracks.")
        parser.add_argument("--region", default=None, help="Region for the imported tracks.")
        parser.add_argument("--primary-mood", default=None, help="Primary mood for the imported tracks.")

    def handle(self, *args, **options):
        scraper = SpotifyScraper()
        imported = 0
        skipped = 0
        
        metadata = {
            "language": options["language"],
            "genre": options["genre"],
            "region": options["region"],
            "primaryMood": options["primary_mood"],
        }

        for url in options["urls"]:
            spotify_id = extract_track_id_from_url(url)
            if not spotify_id:
                self.stderr.write(f"Invalid URL: {url}")
                skipped += 1
                continue
                
            if Track.objects.filter(spotifyId=spotify_id).exists():
                self.stdout.write(f"Track already exists: {spotify_id}")
                skipped += 1
                continue

            payload = scraper.scrape_track(spotify_id)
            if not payload:
                self.stderr.write(f"Failed to scrape: {url}")
                skipped += 1
                continue

            try:
                track = self._create_track(payload, metadata)
                imported += 1
                self.stdout.write(self.style.SUCCESS(f"Imported: {track.title} by {payload['artists']}"))
            except Exception as e:
                self.stderr.write(f"Failed to import {url}: {e}")
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Import finished. Imported={imported} Skipped={skipped}"))

    def _create_track(self, payload: dict, metadata: dict) -> Track:
        artists = payload.get("artists") or ["Unknown Artist"]
        primary_artist_name = artists[0]
        
        with transaction.atomic():
            artist, _ = Artist.objects.get_or_create(
                name=primary_artist_name,
                defaults={"name": primary_artist_name}
            )
            
            track = Track.objects.create(
                spotifyId=payload["spotify_id"],
                title=payload["title"],
                artistId=artist,
                source=Track.SourceChoices.SPOTIFY,
                externalUrl=payload["external_url"],
                durationMs=payload["duration_ms"],
                isExplicit=payload.get("is_explicit", False),
                language=metadata.get("language"),
                genre=metadata.get("genre"),
                region=metadata.get("region"),
                primaryMood=metadata.get("primaryMood"),
            )
            
            # Apply AI inference to fill audio features
            FeatureInferenceService.apply_inference(track, context=metadata)
            
            # Sync to Excel
            transaction.on_commit(lambda: sync_track_to_excel(track))
            
        return track
