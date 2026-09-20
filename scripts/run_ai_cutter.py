"""
End-to-End Local AI Clip Cutter (Personal Edition).

Orchestrates:
  1. Local word-level audio transcription (faster-whisper)
  2. Intelligent high-retention 30–60s clip detection
  3. Face-tracking 9:16 vertical auto-cropping (OpenCV / MediaPipe)
  4. Active kinetic yellow karaoke subtitle generation (ASS safe zone)
  5. Cinematic color grading & final render
  6. Optional YouTube Shorts upload

Usage:
  python run_ai_cutter.py "path/to/movie.mkv"
  python run_ai_cutter.py "path/to/movie.mkv" --top 3
  python run_ai_cutter.py "path/to/movie.mkv" -s 01:41:30 -t 40
  python run_ai_cutter.py "path/to/movie.mkv" --upload
"""

import argparse
import os
import sys

from transcribe import transcribe_video, slugify
from detect_clips import detect_clips
from face_crop import auto_crop_clip
from build_video import build_short_from_clip, get_media_duration, _find_tool
from upload_video import upload_video

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")


def process_video_clip(
    video_path: str,
    start: float,
    duration: float,
    out_path: str,
    transcript_data: dict = None,
    burn_subtitles: bool = True,
) -> str:
    """
    Process a single segment: face-centered vertical crop + kinetic subtitles.
    """
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    slug = slugify(base_name)

    raw_clip_dir = os.path.join(ASSETS, "clips", slug)
    os.makedirs(raw_clip_dir, exist_ok=True)
    raw_clip_path = os.path.join(raw_clip_dir, f"segment_{int(start)}_{int(duration)}_raw.mp4")

    # Step 1: Face-tracking vertical crop
    print(f"\n[1/2] Applying face-tracking 9:16 vertical crop ({start}s -> {start+duration}s)...")
    auto_crop_clip(video_path, start, duration, raw_clip_path)

    # Step 2: Kinetic Subtitles & Color Grading
    if not burn_subtitles or not transcript_data:
        # Move raw clip to output
        import shutil
        shutil.move(raw_clip_path, out_path)
        return out_path

    print("\n[2/2] Generating kinetic karaoke subtitles & cinematic color grade...")

    # Extract word timestamps that fall within this segment
    end = start + duration
    segment_words = []

    for seg in transcript_data.get("segments", []):
        for w in seg.get("words", []):
            w_start = w["start"]
            w_end = w["end"]
            if w_start >= start - 0.2 and w_end <= end + 0.5:
                # Shift timestamp relative to the cut clip (0.0 start)
                rel_start = max(0.0, round(w_start - start, 3))
                rel_end = max(rel_start + 0.05, round(w_end - start, 3))
                segment_words.append({
                    "word": w["word"].strip(),
                    "start": rel_start,
                    "end": rel_end,
                })

    final_short = build_short_from_clip(raw_clip_path, segment_words, out_path)

    # Clean up intermediate raw clip
    try:
        os.remove(raw_clip_path)
    except OSError:
        pass

    return final_short


def main():
    parser = argparse.ArgumentParser(
        description="Local AI Clip Cutter: Automated transcript analysis, face-crop, & kinetic captions."
    )
    parser.add_argument("video", help="Path to input video file")
    parser.add_argument("-s", "--start", type=float, help="Manual start timestamp in seconds")
    parser.add_argument("-t", "--duration", type=float, help="Manual duration in seconds")
    parser.add_argument("-e", "--end", type=float, help="Manual end timestamp in seconds")
    parser.add_argument("--top", type=int, default=1, help="Number of auto-detected clips to export (default: 1)")
    parser.add_argument("--min-dur", type=float, default=30.0, help="Min duration for detected clips (default: 30s)")
    parser.add_argument("--max-dur", type=float, default=60.0, help="Max duration for detected clips (default: 60s)")
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument("--force", action="store_true", help="Rerun transcription from scratch")
    parser.add_argument("--no-subs", action="store_true", help="Do not burn-in subtitles")
    parser.add_argument("--upload", action="store_true", help="Upload rendered Shorts to YouTube")
    parser.add_argument("--schedule", help="Optional ISO 8601 UTC publish time")

    args = parser.parse_args()

    if not os.path.isfile(args.video):
        print(f"ERROR: Video file not found: '{args.video}'", file=sys.stderr)
        sys.exit(1)

    base_name = os.path.splitext(os.path.basename(args.video))[0]
    slug = slugify(base_name)
    out_dir = os.path.join(ASSETS, "output")
    os.makedirs(out_dir, exist_ok=True)

    print(f"=== Local AI Clip Cutter: '{base_name}' ===")

    # Step 1: Transcribe video
    print("\n--- Step 1: Local Word-Level Transcription ---")
    transcript = transcribe_video(args.video, model_size=args.model, force=args.force)

    # Step 2: Determine target cuts
    targets = []

    if args.start is not None:
        if args.duration is not None:
            dur = args.duration
        elif args.end is not None:
            dur = args.end - args.start
        else:
            dur = 30.0
        targets.append({
            "rank": 1,
            "start": args.start,
            "duration": dur,
            "hook": f"Manual Clip from {base_name}",
        })
    else:
        print("\n--- Step 2: Intelligent Clip Detection ---")
        detected = detect_clips(
            args.video,
            transcript=transcript,
            min_duration=args.min_dur,
            max_duration=args.max_dur,
            top_n=args.top,
        )
        for d in detected:
            targets.append({
                "rank": d["rank"],
                "start": d["start"],
                "duration": d["duration"],
                "hook": d.get("hook", f"Clip {d['rank']}"),
                "text": d.get("text", ""),
            })

    if not targets:
        print("No suitable clips identified.")
        sys.exit(0)

    # Step 3: Render each target clip
    print(f"\n--- Step 3: Rendering {len(targets)} Vertical Short(s) ---")
    rendered_shorts = []

    for item in targets:
        rank = item["rank"]
        out_filename = f"{slug}_ai_short_{rank:02d}.mp4"
        out_path = os.path.join(out_dir, out_filename)

        print(f"\n>>> Processing Short #{rank}: {item['duration']}s (starts at {item['start']}s)")
        print(f"Hook: \"{item['hook']}\"")

        short_path = process_video_clip(
            video_path=args.video,
            start=item["start"],
            duration=item["duration"],
            out_path=out_path,
            transcript_data=transcript,
            burn_subtitles=not args.no_subs,
        )
        rendered_shorts.append((short_path, item))
        print(f"SUCCESS: Ready Short created at {short_path}")

    # Step 4: Optional YouTube Upload
    if args.upload:
        print("\n--- Step 4: Publishing to YouTube ---")
        for short_path, item in rendered_shorts:
            title = f"{base_name} — {item['hook'][:40]}"
            desc = (
                f"{item.get('text', item['hook'])}\n\n"
                f"#{slug} #movieclips #shorts"
            )
            upload_video(short_path, title, desc, ["movies", "filmclips", "shorts"], args.schedule)

    print("\n=== All Tasks Completed Successfully ===")
    for short_path, _ in rendered_shorts:
        print(f"  * {short_path}")


if __name__ == "__main__":
    main()
