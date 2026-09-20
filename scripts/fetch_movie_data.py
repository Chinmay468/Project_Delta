"""
Fetch movie metadata + poster image from TMDB (The Movie Database).
TMDB's API is free and its poster images are meant for exactly this kind
of use (discovery/promotion), unlike scraping trailer video frames.

Requires TMDB_API_KEY in config/.env
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "config", ".env"))

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/original"


def fetch_movie(title: str) -> dict:
    if not TMDB_API_KEY:
        print("ERROR: TMDB_API_KEY not set in config/.env")
        sys.exit(1)

    try:
        resp = requests.get(
            f"{BASE_URL}/search/movie",
            params={"api_key": TMDB_API_KEY, "query": title},
            timeout=15,
        )
        search = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"\nERROR: Network request to TMDB failed: {e}")
        print("Tip: If your ISP blocks TMDB (api.themoviedb.org), make sure ProtonVPN is connected and try again.\n")
        sys.exit(1)

    if not resp.ok or "status_message" in search:
        print(f"TMDB API error {resp.status_code}: {search.get('status_message', resp.text)}")
        sys.exit(1)

    if not search.get("results"):
        print(f"No results found for '{title}'")
        sys.exit(1)

    movie = search["results"][0]
    try:
        details = requests.get(
            f"{BASE_URL}/movie/{movie['id']}",
            params={"api_key": TMDB_API_KEY},
            timeout=15,
        ).json()
    except requests.exceptions.RequestException as e:
        print(f"\nERROR: Failed to fetch movie details from TMDB: {e}")
        print("Tip: Ensure your internet connection is active and ProtonVPN is connected.\n")
        sys.exit(1)

    poster_url = f"{IMAGE_BASE}{details['poster_path']}" if details.get("poster_path") else None

    return {
        "title": details["title"],
        "year": (details.get("release_date") or "????")[:4],
        "overview": details.get("overview", ""),
        "tagline": details.get("tagline", ""),
        "genres": [g["name"] for g in details.get("genres", [])],
        "rating": details.get("vote_average"),
        "poster_url": poster_url,
    }


def download_poster(poster_url: str, out_path: str):
    try:
        r = requests.get(poster_url, timeout=20)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"\nERROR: Failed to download poster image: {e}")
        print("Tip: Check your internet and ProtonVPN connection.\n")
        sys.exit(1)
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 fetch_movie_data.py \"Movie Title\"")
        sys.exit(1)
    data = fetch_movie(" ".join(sys.argv[1:]))
    print(data)
