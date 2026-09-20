# Task: Movie Recommendation Shorts Pipeline

## Goal
Build and run an end-to-end pipeline that produces a YouTube Short
recommending a movie, using only legally safe assets (official poster,
public metadata, AI-generated voiceover) and uploads/schedules it to
YouTube via the Data API.

## Do NOT
- Do not download, scrape, or rip any video/trailer footage from YouTube
  or any other platform. This is a hard constraint, not a preference.
- Do not bypass YouTube's ToS in any way (no yt-dlp on copyrighted
  video streams, no proxy scraping of restricted content).

## Pipeline steps (in order)

1. **Fetch movie data** (`scripts/fetch_movie_data.py`)
   Pull title, tagline, overview, release year, and poster image URL from
   TMDB's public API for a given movie title.

2. **Generate script** (`scripts/generate_script.py`)
   Turn the movie data into a ~25-35 second voiceover script following the
   hook-first pattern in `config/script_template.txt`.

3. **Generate voiceover** (`scripts/generate_voiceover.py`)
   Send the script to an AI voice API (ElevenLabs by default) and save the
   resulting audio file to `assets/audio/`.

4. **Build video** (`scripts/build_video.py`)
   Use ffmpeg to combine the poster image (with a slow Ken Burns
   zoom/pan), the voiceover audio, and burned-in captions (generated from
   the script text with timestamps) into a 9:16 vertical video, saved to
   `assets/output/`.

5. **Upload/schedule** (`scripts/upload_video.py`)
   Reuse the existing OAuth flow from the `yt_bulk_edit` project
   (same `client_secret.json` / `token.json` pattern) to upload the video
   with a generated title/description/tags, either publishing immediately
   or scheduling a future publish time.

## Config needed from the user before running
- `TMDB_API_KEY` (free, from themoviedb.org/settings/api)
- `ELEVENLABS_API_KEY` (or swap in another TTS provider)
- `client_secret.json` for the YouTube channel (OAuth, Desktop app type,
  same as the bulk-edit tool)

All keys go in `config/.env` (see `config/.env.example`).

## Definition of done
Running `python3 scripts/run_pipeline.py "Movie Title"` produces a
finished vertical video in `assets/output/` and, if `--upload` is passed,
uploads/schedules it on the connected YouTube channel -- with zero manual
video editing or trailer downloading involved.
