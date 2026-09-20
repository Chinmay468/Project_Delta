"""
End-to-End Autonomous AI Clip Cutter & YouTube Shorts Orchestrator.

Orchestrates:
  Step A: Local word-level audio transcription (faster-whisper) & audio caching (assets/audio/, assets/cache/)
  Step B: Multi-signal Top-N clip curation (detect_clips.py: find_top_n_clips)
  Step C: Batch vertical reframing (face_crop.py: crop_to_vertical) -> assets/clips/<slug>_clip_{i}.mp4
          Kinetic karaoke captions & cinematic grading (build_video.py: burn_subtitles_and_grade) -> assets/output/<slug>_short_{i}.mp4
  Step D: Optional YouTube Shorts staggered upload & scheduling (upload_video.py)

Usage:
  python run_ai_cutter.py "path/to/movie.mkv" -n 3
  python run_ai_cutter.py "path/to/movie.mkv" --min-duration 25 --max-duration 55
  python run_ai_cutter.py "path/to/movie.mkv" --upload --schedule-interval 24
"""

import argparse
from datetime import datetime, timezone, timedelta
import json
import os
import sys

# Ensure scripts dir is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from transcribe import transcribe_video, extract_audio, slugify
from detect_clips import find_top_n_clips, detect_clips
from face_crop import crop_to_vertical, auto_crop_clip
from build_video import burn_subtitles_and_grade, build_short_from_clip, build_karaoke_ass, _find_tool
from upload_video import upload_video

ASSETS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Autonomous AI Clip Cutter & YouTube Shorts Pipeline."
    )
    # Positional required video_path
    parser.add_argument("video_path", help="Path to source video file")

    # -n, --num-clips (default: 3)
    parser.add_argument(
        "-n", "--num-clips",
        type=int,
        default=3,
        help="Total number of distinct clips to extract and render (default: 3)",
    )
    # backward-compatibility alias
    parser.add_argument("--top", type=int, dest="num_clips_alt", help=argparse.SUPPRESS)

    # --min-duration (default: 25.0)
    parser.add_argument(
        "--min-duration",
        type=float,
        default=25.0,
        help="Minimum clip duration in seconds (default: 25.0)",
    )
    parser.add_argument("--min-dur", type=float, dest="min_dur_alt", help=argparse.SUPPRESS)

    # --max-duration (default: 55.0)
    parser.add_argument(
        "--max-duration",
        type=float,
        default=55.0,
        help="Maximum clip duration in seconds (default: 55.0)",
    )
    parser.add_argument("--max-dur", type=float, dest="max_dur_alt", help=argparse.SUPPRESS)

    # --model-size (default: 'base')
    parser.add_argument(
        "--model-size",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument("--model", dest="model_alt", help=argparse.SUPPRESS)

    # --upload (action="store_true")
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Automatically schedule or publish generated shorts to YouTube",
    )

    # --schedule-interval (default: 24.0)
    parser.add_argument(
        "--schedule-interval",
        type=float,
        default=24.0,
        help="Spacing in hours between scheduled releases if --upload is selected (default: 24.0)",
    )

    # --force (action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass cached transcripts and clips, forcing a fresh re-render",
    )

    # Optional manual override
    parser.add_argument("-s", "--start", type=float, help="Manual start timestamp in seconds")
    parser.add_argument("-t", "--duration", type=float, help="Manual duration in seconds")
    parser.add_argument("-e", "--end", type=float, help="Manual end timestamp in seconds")
    parser.add_argument("--no-subs", action="store_true", help="Do not burn subtitles")

    args = parser.parse_args()

    # Reconcile aliases
    if args.num_clips_alt is not None:
        args.num_clips = args.num_clips_alt
    if args.min_dur_alt is not None:
        args.min_duration = args.min_dur_alt
    if args.max_dur_alt is not None:
        args.max_duration = args.max_dur_alt
    if args.model_alt is not None:
        args.model_size = args.model_alt

    return args


def run_orchestrator(args):
    if not os.path.isfile(args.video_path):
        print(f"ERROR: Video file not found: '{args.video_path}'", file=sys.stderr)
        sys.exit(1)

    # Ensure intermediate directories exist
    audio_dir = os.path.join(ASSETS, "audio")
    cache_dir = os.path.join(ASSETS, "cache")
    clips_dir = os.path.join(ASSETS, "clips")
    output_dir = os.path.join(ASSETS, "output")

    for d in [audio_dir, cache_dir, clips_dir, output_dir]:
        os.makedirs(d, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(args.video_path))[0]
    slug = slugify(base_name)

    # ─────────────────────────────────────────────────────────────────────────
    # Step A: Transcription & Word-Timestamp Caching
    # ─────────────────────────────────────────────────────────────────────────
    print("=" * 65)
    print(f"STEP A: Transcription & Word-Timestamp Caching")
    print(f"Target: {args.video_path}")
    print("=" * 65)

    wav_path = os.path.join(audio_dir, f"{slug}_16k.wav")
    if args.force or not os.path.isfile(wav_path) or os.path.getsize(wav_path) == 0:
        print(f"Extracting 16kHz mono audio -> {wav_path}")
        extract_audio(args.video_path, wav_path)
    else:
        print(f"[cached] Audio file: {wav_path}")

    transcript = transcribe_video(
        args.video_path,
        model_size=args.model_size,
        force=args.force,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step B: Curation & Candidate Selection
    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"STEP B: Curation & Candidate Selection (Top-{args.num_clips})")
    print("=" * 65)

    if args.start is not None:
        dur = args.duration if args.duration is not None else ((args.end - args.start) if args.end is not None else 30.0)
        candidates = [{
            "rank": 1,
            "start": round(args.start, 2),
            "end": round(args.start + dur, 2),
            "duration": round(dur, 2),
            "score": 10.0,
            "hook_title": f"Scene Highlight from {base_name}",
            "hook": f"Manual clip at {args.start}s",
            "text": "",
        }]
    else:
        candidates = find_top_n_clips(
            transcript=transcript,
            audio_path=wav_path,
            top_n=args.num_clips,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
        )

    if not candidates:
        print("ERROR: No suitable clips identified by detection engine.", file=sys.stderr)
        sys.exit(1)

    print(f"Discovered {len(candidates)} candidate moments:")
    for c in candidates:
        print(f"  [#{c['rank']}] {c['start']}s -> {c['end']}s ({c['duration']}s) | Score: {c['score']} | Hook: \"{c['hook_title']}\"")

    # ─────────────────────────────────────────────────────────────────────────
    # Step C: Batch Rendering Loop (i = 1 .. N)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"STEP C: Batch Rendering Loop ({len(candidates)} Shorts)")
    print("=" * 65)

    rendered_shorts = []

    for cand in candidates:
        i = cand["rank"]
        start = cand["start"]
        dur = cand["duration"]
        end = cand["end"]
        hook_title = cand.get("hook_title") or cand.get("hook", f"Clip {i}")

        clip_out_path = os.path.join(clips_dir, f"{slug}_clip_{i}.mp4")
        short_out_path = os.path.join(output_dir, f"{slug}_short_{i}.mp4")

        print(f"\n>>> Processing Clip {i}/{len(candidates)}: {hook_title}")
        print(f"Time Interval: {start}s -> {end}s ({dur}s)")

        # 1. Vertical Reframe (face_crop.py: crop_to_vertical)
        if args.force or not os.path.isfile(clip_out_path) or os.path.getsize(clip_out_path) == 0:
            print(f"[1/3] Vertical Reframe (YuNet/Haar 9:16 crop) -> {clip_out_path}")
            crop_to_vertical(args.video_path, start, dur, clip_out_path)
        else:
            print(f"[1/3] [cached] Using existing vertical crop: {clip_out_path}")

        # 2. Word Slicing & ASS Karaoke Generation
        print(f"[2/3] Slicing transcript words for [{start}s - {end}s]...")
        segment_words = []
        for seg in transcript.get("segments", []):
            for w in seg.get("words", []):
                ws = float(w["start"])
                we = float(w["end"])
                if ws >= start - 0.2 and we <= end + 0.5:
                    rel_start = max(0.0, round(ws - start, 3))
                    rel_end = max(rel_start + 0.05, round(we - start, 3))
                    segment_words.append({
                        "word": w["word"].strip(),
                        "start": rel_start,
                        "end": rel_end,
                    })

        # 3. Cinematic Grading & Subtitle Burn (build_video.py: burn_subtitles_and_grade)
        if args.no_subs:
            print(f"[3/3] Subtitles disabled. Copying raw vertical clip -> {short_out_path}")
            import shutil
            shutil.copyfile(clip_out_path, short_out_path)
            final_short = short_out_path
        else:
            print(f"[3/3] Burning kinetic karaoke captions & cinematic grade -> {short_out_path}")
            final_short = burn_subtitles_and_grade(
                video_path=clip_out_path,
                words_data=segment_words,
                out_path=short_out_path,
            )

        rendered_shorts.append({
            "rank": i,
            "short_path": final_short,
            "candidate": cand,
        })
        print(f" SUCCESS: Short #{i} generated at {final_short}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step D: Optional YouTube Deployment
    # ─────────────────────────────────────────────────────────────────────────
    if args.upload:
        print("\n" + "=" * 65)
        print("STEP D: YouTube Shorts Deployment")
        print("=" * 65)
        now_utc = datetime.now(timezone.utc)
        for idx, item in enumerate(rendered_shorts):
            short_path = item["short_path"]
            cand = item["candidate"]
            hook_title = cand.get("hook_title", f"Clip {item['rank']}")

            # Title format: "{hook_title} #shorts"
            title = f"{hook_title} #shorts"
            if len(title) > 100:
                title = title[:90] + " #shorts"

            desc = f"{cand.get('text', hook_title)}\n\n#{slug} #movieclips #shorts"

            # Compute staggered publish timestamps
            publish_time = now_utc + timedelta(hours=idx * args.schedule_interval)
            publish_iso = publish_time.strftime("%Y-%m-%dT%H:%M:%SZ")

            print(f"\nUploading Short #{item['rank']}: '{title}'")
            print(f"Scheduled publish at: {publish_iso}")

            try:
                video_id = upload_video(
                    short_path,
                    title=title,
                    description=desc,
                    tags=["movies", "filmclips", "shorts"],
                    publish_at=publish_iso,
                )
                print(f" Upload successful! Video ID: {video_id}")
            except Exception as e:
                print(f" Upload error for Short #{item['rank']}: {e}", file=sys.stderr)

    print("\n" + "=" * 65)
    print("PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"Total Shorts Rendered: {len(rendered_shorts)}")
    for item in rendered_shorts:
        print(f"  * Short #{item['rank']}: {item['short_path']}")
    print("=" * 65)
    return rendered_shorts


def main():
    args = parse_args()
    run_orchestrator(args)


if __name__ == "__main__":
    main()
