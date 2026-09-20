"""
Standalone video clip cutter utility for movie-shorts-pipeline.

Extracts clips from local video files using ffmpeg without re-encoding (--copy)
or with frame-accurate vertical 9:16 reformatting (--vertical).

Legal & Compliance Note:
  This tool is strictly designed for local video files.
  Do NOT add scrapers, stream rippers, or automated video downloaders.
"""

import argparse
import os
import re
import subprocess
import sys

# ── Tool resolver ────────────────────────────────────────────────────────────

try:
    from build_video import _find_tool
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from build_video import _find_tool


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def cut_clip(
    input_path: str,
    start: str,
    end: str = None,
    duration: str = None,
    output_path: str = None,
    copy: bool = False,
    vertical: bool = False,
) -> str:
    """
    Extract a clip from input_path using ffmpeg.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Source video file not found: '{input_path}'")

    if not end and not duration:
        raise ValueError("Either 'end' timestamp or 'duration' must be provided.")

    if end and duration:
        raise ValueError("Specify either 'end' timestamp or 'duration', not both.")

    if copy and vertical:
        raise ValueError("Cannot combine --copy with --vertical (vertical reformatting requires re-encoding).")

    # Determine output destination
    if not output_path:
        assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
        clips_dir = os.path.join(assets_dir, "clips")
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        slug = slugify(base_name)
        output_path = os.path.join(clips_dir, f"{slug}_cut.mp4")

    out_abs = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)

    input_abs = os.path.abspath(input_path)
    ffmpeg_bin = _find_tool("ffmpeg")

    # Construct ffmpeg command
    cmd = [ffmpeg_bin, "-y", "-ss", str(start)]

    if duration:
        cmd.extend(["-t", str(duration)])
    elif end:
        cmd.extend(["-to", str(end)])

    cmd.extend(["-i", input_abs])

    if copy:
        # Lossless stream copy for instantaneous cut
        cmd.extend(["-c", "copy", "-avoid_negative_ts", "1"])
    elif vertical:
        # Vertical 9:16 (1080x1920) re-encoding matching build_video.py standard
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        cmd.extend([
            "-vf", vf,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
        ])
    else:
        # Standard frame-accurate re-encode preserving aspect ratio
        cmd.extend([
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
        ])

    cmd.append(out_abs)

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: ffmpeg failed with exit code {e.returncode}:", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        raise

    return out_abs


def cut_clips(
    input_path: str,
    cuts: list,
    out_dir: str = None,
    vertical: bool = True,
    copy: bool = False,
) -> list:
    """
    Cut multiple scene segments from input_path.

    cuts: list of dicts with keys:
      - 'start': start timestamp
      - 'duration' or 'end': cut boundary
      - optional 'name': base name for output file (e.g. 'clip_01.mp4')
    """
    if not out_dir:
        assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        out_dir = os.path.join(assets_dir, "clips", slugify(base_name))

    os.makedirs(out_dir, exist_ok=True)
    results = []

    for i, cut in enumerate(cuts):
        name = cut.get("name") or f"clip_{i+1:02d}.mp4"
        out_path = os.path.join(out_dir, name)
        saved = cut_clip(
            input_path=input_path,
            start=cut["start"],
            end=cut.get("end"),
            duration=cut.get("duration"),
            output_path=out_path,
            copy=copy,
            vertical=vertical,
        )
        results.append(saved)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Cut video clips from local files using ffmpeg (lossless copy or vertical 9:16)."
    )
    parser.add_argument("input", help="Path to source video file")
    parser.add_argument("-s", "--start", required=True, help="Start timestamp (e.g. 00:01:23, 83, 14.5)")

    group_time = parser.add_mutually_exclusive_group(required=True)
    group_time.add_argument("-e", "--end", "--to", dest="end", help="Cut end timestamp (e.g. 00:01:33, 93)")
    group_time.add_argument("-t", "--duration", help="Total duration to cut (e.g. 10, 00:00:10)")

    parser.add_argument("-o", "--output", help="Destination path for cut clip")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--copy",
        action="store_true",
        help="Lossless stream copy (-c copy -avoid_negative_ts 1) for instant cutting",
    )
    mode_group.add_argument(
        "--vertical",
        action="store_true",
        help="Re-encode to vertical 9:16 format (1080x1920)",
    )

    args = parser.parse_args()

    try:
        saved_path = cut_clip(
            input_path=args.input,
            start=args.start,
            end=args.end,
            duration=args.duration,
            output_path=args.output,
            copy=args.copy,
            vertical=args.vertical,
        )
        print(f"Clip saved successfully: {saved_path}")
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError:
        sys.exit(1)


if __name__ == "__main__":
    main()
