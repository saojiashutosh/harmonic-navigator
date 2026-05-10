"""
Fetch Spotify playlist tracks and save as JSON for import into the app.

HOW TO GET YOUR SPOTIFY TOKEN:
  1. Open https://open.spotify.com in your browser (log in if needed)
  2. Press F12 → Console tab
  3. Paste this and press Enter:
       (await fetch('/get_access_token?reason=transport&productType=web_player').then(r=>r.json())).accessToken
  4. Copy the long token string that appears

Then run this script:
    python fetch_playlist.py <playlist_url> <output.json> --token <your_token>

Example:
    python fetch_playlist.py "https://open.spotify.com/playlist/27uD2cElvkSceHpdXs2AFg" 90s.json --token BQC...

Multiple playlists:
    python fetch_playlist.py URL1 file1.json --token TOKEN
    python fetch_playlist.py URL2 file2.json --token TOKEN
"""
import sys
import json
import urllib.request
import argparse


def fetch_playlist_tracks(playlist_id, token):
    tracks = []
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit=100&offset=0"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    while url:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                page = json.loads(resp.read())
        except urllib.request.HTTPError as e:
            body = e.read().decode()
            raise RuntimeError(f"HTTP {e.code}: {body}") from e

        for item in page.get("items", []):
            track = item.get("track")
            if not track or track.get("type") != "track":
                continue
            artist = (track.get("artists") or [{}])[0]
            tracks.append({
                "spotify_id": track.get("id"),
                "title": track.get("name"),
                "artist_name": artist.get("name"),
                "artist_spotify_id": artist.get("id"),
                "duration_ms": track.get("duration_ms"),
                "is_explicit": bool(track.get("explicit", False)),
                "preview_url": track.get("preview_url"),
                "external_url": (track.get("external_urls") or {}).get("spotify"),
                "release_date": (track.get("album") or {}).get("release_date"),
            })
        url = page.get("next")
        print(f"  {len(tracks)} tracks fetched...")
    return tracks


def extract_playlist_id(url):
    return url.split("/playlist/")[-1].split("?")[0].strip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("playlist_url")
    parser.add_argument("output_file")
    parser.add_argument("--token", required=True, help="Spotify access token from browser console")
    args = parser.parse_args()

    playlist_id = extract_playlist_id(args.playlist_url)
    print(f"Playlist ID: {playlist_id}")
    print("Fetching tracks...")

    tracks = fetch_playlist_tracks(playlist_id, args.token)
    print(f"Total: {len(tracks)} tracks")

    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(tracks, f, ensure_ascii=False, indent=2)
    print(f"Saved to {args.output_file}")
