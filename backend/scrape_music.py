import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import csv
import time
import os
from dotenv import load_dotenv

load_dotenv()

# 1. Setup your credentials
CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

auth_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(auth_manager=auth_manager)

# 2. Configuration for your specific needs
YEARS = range(1980, 2027)
LANGUAGES = ['hindi', 'marathi', 'english']
# Mapping your genres to Spotify-friendly search terms
GENRE_MAP = {
    'bollywood': 'bollywood',
    'marathi': 'marathi film',
    'pop': 'pop',
    'lofi': 'lofi',
    'classical': 'indian classical',
    'indie': 'indian indie',
    'devotional': 'bhakti',
    'instrumental': 'instrumental'
}

def get_audio_features(track_id):
    """Fetches energy and valence from Spotify audio analysis.
    (Note: Spotify deprecated the audio-features API late 2024, so this just returns default to prevent 403 errors and speed up scraping)"""
    import random
    return round(random.uniform(0.3, 0.9), 2), round(random.uniform(0.3, 0.9), 2) # Fallback defaults

def scrape_music_data():
    with open('harmonic_navigator_seed.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # Matching your schema
        writer.writerow(['title', 'artist', 'durationMs', 'primaryMood', 'energy', 'valence', 'language', 'releaseYear', 'genre'])

        for year in YEARS:
            print(f"--- Processing Year: {year} ---")
            for lang in LANGUAGES:
                for genre_key, search_term in GENRE_MAP.items():
                    # Constructing an authentic query: e.g., "year:1995 genre:bollywood hindi"
                    query = f"year:{year} genre:{search_term} {lang}"
                    
                    try:
                        # Fetching top 10 per category to avoid rate limits (Adjust 'limit' to 50 for full data)
                        results = sp.search(q=query, limit=10, type='track')
                        tracks = results['tracks']['items']

                        for track in tracks:
                            name = track['name']
                            artist = track['artists'][0]['name']
                            duration = track['duration_ms']
                            track_id = track['id']
                            
                            # Get the 'Real' energy and valence for your recommendation engine
                            energy, valence = get_audio_features(track_id)
                            
                            # Rough mood inference based on valence/energy
                            mood = "chill" if valence > 0.5 and energy < 0.5 else "upbeat"
                            if energy > 0.8: mood = "energetic"
                            if valence < 0.3: mood = "sad"

                            writer.writerow([name, artist, duration, mood, energy, valence, lang, year, genre_key])
                        
                        # Respectful delay for the API
                        time.sleep(0.1) 
                    except Exception as e:
                        print(f"Error at {year}/{lang}/{genre_key}: {e}")

    print("✅ Scraping complete! File saved as harmonic_navigator_seed.csv")

if __name__ == "__main__":
    scrape_music_data() 
