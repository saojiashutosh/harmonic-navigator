import re
import requests
from typing import Dict, Optional

class SpotifyScraper:
    """
    A lightweight scraper to extract track metadata from public Spotify pages.
    """
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def scrape_track(self, spotify_id: str) -> Optional[Dict]:
        url = f"https://open.spotify.com/track/{spotify_id}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                return None
            
            html = resp.text
            
            # Extract basic metadata using regex
            title_match = re.search(r'<title>(.*?) - song and lyrics by (.*?) \| Spotify</title>', html)
            if not title_match:
                title_match = re.search(r'<title>(.*?) \| Spotify</title>', html)
            
            title = title_match.group(1).strip() if title_match else None
            artists_str = title_match.group(2).strip() if (title_match and len(title_match.groups()) > 1) else None
            
            # Extract from OG tags if title failed
            if not title:
                og_title = re.search(r'<meta property="og:title" content="(.*?)"', html)
                title = og_title.group(1) if og_title else None
                
            og_description = re.search(r'<meta property="og:description" content="(.*?)"', html)
            description = og_description.group(1) if og_description else ""
            
            # Description format: "Artist1, Artist2 · SongTitle · Song · Year"
            # Or "Artist · Album · Song · Year"
            
            # Extract Duration (often in JSON-LD or schema.org)
            duration_match = re.search(r'"duration":\s*"PT(\d+)M(\d+)S"', html)
            duration_ms = None
            if duration_match:
                minutes = int(duration_match.group(1))
                seconds = int(duration_match.group(2))
                duration_ms = (minutes * 60 + seconds) * 1000
            
            # Fallback duration from metadata
            if not duration_ms:
                # Some pages have duration in ms in JSON
                ms_match = re.search(r'"duration_ms":(\d+)', html)
                if ms_match:
                    duration_ms = int(ms_match.group(1))

            # Extract Year
            year_match = re.search(r'· (\d{4})', description)
            year = year_match.group(1) if year_match else None
            
            # Extract Album
            album = None
            if "·" in description:
                parts = description.split("·")
                if len(parts) >= 2:
                    album = parts[1].strip()

            return {
                "spotify_id": spotify_id,
                "title": title,
                "artists": [a.strip() for a in (artists_str.split(",") if artists_str else [])],
                "duration_ms": duration_ms,
                "release_year": year,
                "album_name": album,
                "external_url": url,
                "is_explicit": "Explicit" in html or '"explicit": true' in html.lower(),
            }
        except Exception:
            return None

def extract_track_id_from_url(url: str) -> Optional[str]:
    match = re.search(r"track/([A-Za-z0-9]{22})", url)
    return match.group(1) if match else None
