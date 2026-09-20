"""
Validation script for Layer 3: Kinetic Karaoke Captions & Visual Grading.
Tests build_karaoke_ass and burn_subtitles_and_grade on a 30s cut with Whisper timestamps.
"""

import json
import os
import subprocess
import sys

# Ensure scripts dir is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from build_video import (
    build_karaoke_ass,
    burn_subtitles_and_grade,
    load_words_from_transcript,
    _find_tool,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
CACHE_DIR = os.path.join(ASSETS_DIR, "cache")
CLIPS_DIR = os.path.join(ASSETS_DIR, "clips")
OUTPUT_DIR = os.path.join(ASSETS_DIR, "output")

SOURCE_VIDEO = os.path.join(CLIPS_DIR, "the_usual_suspects_devil_trick_40s_vertical.mp4")
TRANSCRIPT_JSON = os.path.join(CACHE_DIR, "the_usual_suspects_devil_trick_40s_vertical_transcript.json")

CUT_VIDEO = os.path.join(CLIPS_DIR, "test_30s_cut.mp4")
OUT_SHORT = os.path.join(OUTPUT_DIR, "test_30s_karaoke_short.mp4")
OUT_ASS = os.path.join(OUTPUT_DIR, "test_30s_karaoke_short.ass")


def main():
    print("=" * 60)
    print("Layer 3 Validation: Kinetic Karaoke Captions & Visual Grading")
    print("=" * 60)

    # 1. Verify source files exist
    assert os.path.isfile(SOURCE_VIDEO), f"Source video not found: {SOURCE_VIDEO}"
    assert os.path.isfile(TRANSCRIPT_JSON), f"Transcript JSON not found: {TRANSCRIPT_JSON}"

    # 2. Extract a 30s cut (0.0s to 30.0s)
    print(f"\n[Step 1] Cutting 30.0s segment from source video...")
    ffmpeg = _find_tool("ffmpeg")
    cut_cmd = [
        ffmpeg, "-y",
        "-ss", "0.0",
        "-i", SOURCE_VIDEO,
        "-t", "30.0",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        CUT_VIDEO,
    ]
    subprocess.run(cut_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f" Cut saved: {CUT_VIDEO}")

    # 3. Load words from transcript and slice to 30s
    print(f"\n[Step 2] Slicing Whisper word timestamps for [0.0s - 30.0s]...")
    all_words = load_words_from_transcript(TRANSCRIPT_JSON)
    cut_words = [w for w in all_words if float(w["start"]) < 30.0]
    print(f" Total words in 30s cut: {len(cut_words)}")
    print(f" First 3 words: {cut_words[:3]}")
    print(f" Last 3 words: {cut_words[-3:]}")

    # 4. Generate Karaoke ASS Subtitles
    print(f"\n[Step 3] Generating Kinetic Karaoke ASS Subtitles...")
    build_karaoke_ass(cut_words, OUT_ASS)
    assert os.path.isfile(OUT_ASS), f"ASS file was not created: {OUT_ASS}"
    print(f" Karaoke ASS generated: {OUT_ASS}")

    with open(OUT_ASS, "r", encoding="utf-8") as f:
        ass_content = f.read()

    # Check key requirements
    assert "PlayResX: 1080" in ass_content
    assert "PlayResY: 1920" in ass_content
    assert "Fontsize, PrimaryColour" in ass_content or "Fontsize" in ass_content
    assert "80,&H00FFFFFF" in ass_content, "FontSize=80 or base white not found"
    assert "240,1" in ass_content, "MarginV=240 not found"
    assert "\\c&H00FFFF&" in ass_content, "Yellow highlight tag &H00FFFF& not found"
    print(" Verified ASS Style: PlayRes=1080x1920, FontSize=80, Base=&H00FFFFFF&, Highlight=&H00FFFF&, MarginV=240")

    # 5. Burn subtitles & apply cinematic grade
    print(f"\n[Step 4] Burning subtitles & applying cinematic color grade via FFmpeg...")
    rendered_path = burn_subtitles_and_grade(CUT_VIDEO, cut_words, OUT_SHORT)
    assert os.path.isfile(rendered_path), f"Rendered short not found: {rendered_path}"
    print(f" Rendered Short: {rendered_path}")

    # 6. Check probe info
    ffprobe = _find_tool("ffprobe")
    probe_cmd = [
        ffprobe, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration",
        "-of", "json",
        rendered_path,
    ]
    probe_out = subprocess.check_output(probe_cmd, text=True)
    probe_data = json.loads(probe_out)["streams"][0]
    width = int(probe_data["width"])
    height = int(probe_data["height"])
    print(f"\n[Step 5] Validating output format:")
    print(f" Dimensions: {width}x{height} (Expected: 1080x1920)")
    assert width == 1080 and height == 1920, f"Unexpected dimensions: {width}x{height}"

    # 7. Extract verification frames at specific word highlight timestamps
    # Look for active timestamps in cut_words
    # E.g. at ~28.3s ("never")
    print(f"\n[Step 6] Extracting verification frames showing active yellow highlight...")
    frame_times = [2.5, 14.5, 28.3]
    extracted_frames = []

    for t in frame_times:
        frame_name = f"karaoke_frame_{int(t*10)}s.jpg"
        frame_out = os.path.join(OUTPUT_DIR, frame_name)
        snap_cmd = [
            ffmpeg, "-y",
            "-ss", str(t),
            "-i", rendered_path,
            "-vframes", "1",
            "-q:v", "2",
            frame_out,
        ]
        subprocess.run(snap_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.isfile(frame_out):
            extracted_frames.append(frame_out)
            print(f" Extracted frame at {t}s -> {frame_out}")

    print("\n" + "=" * 60)
    print("LAYER 3 VALIDATION COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
