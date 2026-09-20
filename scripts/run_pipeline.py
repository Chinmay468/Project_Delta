"""
End-to-end orchestrator: movie title in -> finished (and optionally
uploaded) high-retention Short out.

Supports both:
  1. Multi-clip mystery engine (default):
     - Open-Loop Mystery script breakdown (50–75 words)
     - Multi-scene dynamic cuts from assets/clips/<slug>/ or --clips
     - Cinematic color grading (eq filter)
     - Safe-margin burned-in ASS captions (MarginV=240)
  2. Poster slideshow (fallback when no video clips are present)
"""

import argparse
import glob
import json
import os
import re

from fetch_movie_data import fetch_movie, download_poster
from generate_script import build_script
from generate_voiceover import generate_voiceover
from build_video import build_video, build_multi_clip_video
from upload_video import upload_video

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _skip(path: str, label: str, force: bool) -> bool:
    """Return True (and print a skip message) if path exists and --force is off."""
    if not force and os.path.exists(path) and os.path.getsize(path) > 0:
        print(f"    [cached] {label} already exists, skipping.")
        return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Run end-to-end movie Shorts pipeline (Mystery or Review mode)."
    )
    parser.add_argument("title", help="Movie title to build a Short about")
    parser.add_argument(
        "--mode",
        choices=["mystery", "review"],
        default="mystery",
        help="Shorts formula mode (default: mystery)",
    )
    parser.add_argument(
        "--clips",
        nargs="*",
        help="Optional paths to specific video clips to assemble (overrides auto-detection)",
    )
    parser.add_argument("--upload", action="store_true", help="Upload to YouTube after building")
    parser.add_argument("--schedule", help="ISO 8601 UTC publish time, e.g. 2026-09-25T14:00:00Z")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached files and regenerate everything from scratch",
    )
    args = parser.parse_args()

    # Ensure all asset directories exist
    for subdir in ("cache", "posters", "audio", "output", "clips"):
        os.makedirs(os.path.join(ASSETS, subdir), exist_ok=True)

    # ── Step 1: Fetch movie data (cached as JSON) ─────────────────────────────
    print(f"1/5 Fetching movie data for '{args.title}'...")
    input_slug = slugify(args.title)
    cache_path = os.path.join(ASSETS, "cache", f"{input_slug}.json")

    if _skip(cache_path, f"movie data cache ({cache_path})", args.force):
        with open(cache_path, encoding="utf-8") as f:
            movie = json.load(f)
    else:
        movie = fetch_movie(args.title)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(movie, f, ensure_ascii=False, indent=2)

    slug = slugify(movie["title"])

    canonical_cache = os.path.join(ASSETS, "cache", f"{slug}.json")
    if slug != input_slug and not os.path.exists(canonical_cache):
        with open(canonical_cache, "w", encoding="utf-8") as f:
            json.dump(movie, f, ensure_ascii=False, indent=2)

    # ── Step 2: Download poster ───────────────────────────────────────────────
    print("2/5 Downloading poster...")
    poster_path = os.path.join(ASSETS, "posters", f"{slug}.jpg")
    if not _skip(poster_path, f"poster ({slug}.jpg)", args.force):
        if not movie.get("poster_url"):
            print("    WARNING: no poster URL in movie data, skipping download.")
        else:
            download_poster(movie["poster_url"], poster_path)

    # ── Step 3: Generate script ───────────────────────────────────────────────
    print(f"3/5 Generating script ({args.mode} mode)...")
    script_text = build_script(movie, mode=args.mode)
    word_count = len(script_text.split())
    print(f"    Script ({word_count} words): {script_text}")

    # ── Step 4: Generate voiceover ────────────────────────────────────────────
    print("4/5 Generating voiceover...")
    audio_path = os.path.join(ASSETS, "audio", f"{slug}.mp3")
    if not _skip(audio_path, f"voiceover ({slug}.mp3)", args.force):
        generate_voiceover(script_text, audio_path)

    # ── Step 5: Build video ───────────────────────────────────────────────────
    print("5/5 Building video...")
    video_path = os.path.join(ASSETS, "output", f"{slug}.mp4")

    # Clip discovery logic
    discovered_clips = []
    if args.clips:
        discovered_clips = [os.path.abspath(c) for c in args.clips]
    else:
        slug_clips_dir = os.path.join(ASSETS, "clips", slug)
        if os.path.isdir(slug_clips_dir):
            discovered_clips = sorted(glob.glob(os.path.join(slug_clips_dir, "*.mp4")))

    if not _skip(video_path, f"video ({slug}.mp4)", args.force):
        if discovered_clips:
            print(f"    [Multi-Clip Engine] Assembling {len(discovered_clips)} clips with cinematic color grade...")
            build_multi_clip_video(discovered_clips, audio_path, script_text, video_path)
        else:
            print("    [Notice] No scene clips found in assets/clips/<slug>/. Falling back to poster zoom slideshow...")
            build_video(poster_path, audio_path, script_text, video_path)
    print(f"Video ready: {video_path}")

    # ── Optional: upload ──────────────────────────────────────────────────────
    if args.upload:
        if args.mode == "mystery":
            title = f"{movie['title']} ({movie['year']}) — The Ending You Missed"
        else:
            title = f"{movie['title']} ({movie['year']}) — Should You Watch It?"

        description = (
            f"{script_text}\n\n"
            f"#{slugify(movie['title'])} #moviemystery #filmtheory #shorts"
        )
        upload_video(video_path, title, description,
                     ["movies", "moviemystery", "shorts"], args.schedule)


if __name__ == "__main__":
    main()
