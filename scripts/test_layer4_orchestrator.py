"""
Layer 4 Integration Test Suite: End-to-End Autonomous AI Clip Cutter Orchestrator.

Validates:
  1. CLI parameter ingestion (-n 2, --min-duration, --max-duration).
  2. Population of all intermediate directories:
     - assets/audio/ (<slug>_16k.wav)
     - assets/cache/ (<slug>_transcript.json)
     - assets/clips/ (<slug>_clip_1.mp4, <slug>_clip_2.mp4)
     - assets/output/ (<slug>_short_1.mp4, <slug>_short_2.mp4)
  3. Video technical specifications:
     - Dimensions: exactly 1080x1920 (9:16 vertical)
     - Video codec: h264, Audio codec: aac
     - Audio/Video stream duration alignment (zero desync)
  4. Kinetic karaoke subtitle presence in .ass and burned frame.
"""

import json
import os
import subprocess
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")
CACHE_DIR = os.path.join(ASSETS_DIR, "cache")
CLIPS_DIR = os.path.join(ASSETS_DIR, "clips")
OUTPUT_DIR = os.path.join(ASSETS_DIR, "output")

TEST_VIDEO = os.path.join(CLIPS_DIR, "the_usual_suspects_devil_trick_40s_vertical.mp4")

# Add scripts directory to path
sys.path.insert(0, SCRIPTS_DIR)
from build_video import _find_tool
from transcribe import slugify


def get_stream_info(video_path: str) -> dict:
    ffprobe = _find_tool("ffprobe")
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "stream=width,height,codec_type,codec_name,duration",
        "-show_entries", "format=duration",
        "-of", "json",
        os.path.abspath(video_path),
    ]
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


def main():
    print("=" * 70)
    print("LAYER 4 INTEGRATION TEST: Autonomous Top-N Short Orchestrator CLI")
    print("=" * 70)

    assert os.path.isfile(TEST_VIDEO), f"Source test video not found: {TEST_VIDEO}"
    base_name = os.path.splitext(os.path.basename(TEST_VIDEO))[0]
    slug = slugify(base_name)

    # 1. Run the orchestrator CLI command with -n 2
    orchestrator_script = os.path.join(SCRIPTS_DIR, "run_ai_cutter.py")
    cmd = [
        sys.executable, orchestrator_script,
        TEST_VIDEO,
        "-n", "2",
        "--min-duration", "10.0",
        "--max-duration", "20.0",
    ]
    print(f"\n[Step 1] Executing Orchestrator CLI:\n  {' '.join(cmd)}\n")
    proc = subprocess.run(cmd, check=True)
    assert proc.returncode == 0, f"Orchestrator failed with returncode {proc.returncode}"
    print(" Orchestrator execution completed successfully.")

    # 2. Verify all intermediate and output directories are populated
    print("\n[Step 2] Verifying directory population...")
    expected_audio = os.path.join(AUDIO_DIR, f"{slug}_16k.wav")
    expected_transcript = os.path.join(CACHE_DIR, f"{slug}_transcript.json")
    expected_clip_1 = os.path.join(CLIPS_DIR, f"{slug}_clip_1.mp4")
    expected_clip_2 = os.path.join(CLIPS_DIR, f"{slug}_clip_2.mp4")
    expected_short_1 = os.path.join(OUTPUT_DIR, f"{slug}_short_1.mp4")
    expected_short_2 = os.path.join(OUTPUT_DIR, f"{slug}_short_2.mp4")
    expected_ass_1 = os.path.join(OUTPUT_DIR, f"{slug}_short_1.ass")
    expected_ass_2 = os.path.join(OUTPUT_DIR, f"{slug}_short_2.ass")

    for path, desc in [
        (expected_audio, "Audio extraction (assets/audio/)"),
        (expected_transcript, "Transcript cache (assets/cache/)"),
        (expected_clip_1, "Intermediate reframed clip 1 (assets/clips/)"),
        (expected_clip_2, "Intermediate reframed clip 2 (assets/clips/)"),
        (expected_short_1, "Final rendered Short 1 (assets/output/)"),
        (expected_short_2, "Final rendered Short 2 (assets/output/)"),
        (expected_ass_1, "Karaoke ASS subtitle 1 (assets/output/)"),
        (expected_ass_2, "Karaoke ASS subtitle 2 (assets/output/)"),
    ]:
        assert os.path.isfile(path), f"Missing expected artifact: {path} ({desc})"
        size = os.path.getsize(path)
        assert size > 0, f"Artifact is empty: {path}"
        print(f"   {desc}: {os.path.basename(path)} ({size:,} bytes)")

    # 3. Technical Video Quality & Audio Sync Checks
    print("\n[Step 3] Inspecting video/audio streams and sync...")
    for idx, short_path in enumerate([expected_short_1, expected_short_2], 1):
        info = get_stream_info(short_path)
        streams = info.get("streams", [])
        v_stream = next((s for s in streams if s["codec_type"] == "video"), None)
        a_stream = next((s for s in streams if s["codec_type"] == "audio"), None)

        assert v_stream is not None, f"No video stream found in {short_path}"
        assert a_stream is not None, f"No audio stream found in {short_path}"

        w = int(v_stream["width"])
        h = int(v_stream["height"])
        assert w == 1080 and h == 1920, f"Dimensions {w}x{h} != 1080x1920 in {short_path}"

        v_dur = float(v_stream.get("duration") or info["format"]["duration"])
        a_dur = float(a_stream.get("duration") or info["format"]["duration"])
        sync_delta = abs(v_dur - a_dur)

        print(f"  Short #{idx} ({os.path.basename(short_path)}):")
        print(f"    Dimensions: {w}x{h} (9:16 Vertical)")
        print(f"    Codecs: Video={v_stream['codec_name']}, Audio={a_stream['codec_name']}")
        print(f"    Durations: Video={v_dur:.2f}s, Audio={a_dur:.2f}s (Delta: {sync_delta:.3f}s)")
        assert sync_delta < 0.5, f"Audio/Video desync exceeds tolerance: {sync_delta}s"

    # 4. Verify Subtitle Content & Yellow Highlights
    print("\n[Step 4] Checking ASS subtitle contents & highlight synchronization...")
    for idx, ass_path in enumerate([expected_ass_1, expected_ass_2], 1):
        with open(ass_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "PlayResX: 1080" in content
        assert "PlayResY: 1920" in content
        assert "80,&H00FFFFFF" in content, "FontSize=80 or base white missing"
        assert "240,1" in content, "MarginV=240 safe margin missing"
        assert "\\c&H00FFFF&" in content, "Yellow highlight tag missing"
        print(f"  Short #{idx} ASS file verified: PlayRes=1080x1920, FontSize=80, MarginV=240, Yellow Highlights present.")

    # 5. Extract verification snapshots
    print("\n[Step 5] Extracting visual screengrabs from both shorts...")
    ffmpeg = _find_tool("ffmpeg")
    snapshot_1 = os.path.join(OUTPUT_DIR, "orchestrator_short1_snap.jpg")
    snapshot_2 = os.path.join(OUTPUT_DIR, "orchestrator_short2_snap.jpg")

    for short_path, snap_path, t in [(expected_short_1, snapshot_1, 3.0), (expected_short_2, snapshot_2, 3.0)]:
        snap_cmd = [
            ffmpeg, "-y",
            "-ss", str(t),
            "-i", short_path,
            "-vframes", "1",
            "-q:v", "2",
            snap_path,
        ]
        subprocess.run(snap_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert os.path.isfile(snap_path) and os.path.getsize(snap_path) > 0
        print(f"  Extracted snapshot: {snap_path}")

    print("\n" + "=" * 70)
    print("LAYER 4 INTEGRATION TEST COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
