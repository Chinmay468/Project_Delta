"""
Project Delta — Autonomous AI Movie Shorts Studio
Interactive Menu-Driven Terminal Interface.

Provides intuitive, interactive access to:
  1. Autonomous AI Top-N Viral Shorts Cutter (Transcribe -> Curate -> YuNet Crop -> Karaoke -> Grade)
  2. Manual Scene Extraction (Custom start timestamp, duration, face-crop, and captions)
  3. Movie Mystery Breakdown Engine (Script generation, voiceover, multi-clip / poster)
  4. Modular Pipeline Tools (Transcribe, Detect Moments, Face Crop, Burn Subtitles, Upload)
  5. Gallery & Output Manager (Inspect & launch rendered Shorts in Windows Player/Explorer)
  6. Health Check & API Key Status (FFmpeg, YuNet, ElevenLabs, TMDB, YouTube OAuth)
"""

import os
import sys
import subprocess
import re
import json
from datetime import datetime, timezone, timedelta

# Ensure repo root and scripts are in sys.path
REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")
CONFIG_DIR = os.path.join(REPO_ROOT, "config")

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, SCRIPTS_DIR)

from build_video import _find_tool, burn_subtitles_and_grade, build_karaoke_ass
from transcribe import transcribe_video, slugify, extract_audio
from detect_clips import find_top_n_clips, detect_clips
from face_crop import crop_to_vertical, get_face_detector
from cut_clip import cut_clip

# ANSI Color formatting (supported by modern Windows PowerShell / CMD)
class Colors:
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def clear_screen():
    """Clear terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    """Wait for user keypress to return to menu."""
    print(f"\n{Colors.DIM}Press Enter to return to main menu...{Colors.RESET}", end="")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass


def print_header(title: str = "PROJECT DELTA — AI MOVIE SHORTS STUDIO"):
    clear_screen()
    print(f"{Colors.CYAN}{Colors.BOLD}=" * 76)
    print(f"  {title}")
    print(f"  Autonomous AI Clip Cutter • Mystery Breakdown • Kinetic Subtitles")
    print(f"=" * 76 + f"{Colors.RESET}\n")


def clean_input_path(raw: str) -> str:
    """Clean user input path, stripping quotes and surrounding whitespace."""
    if not raw:
        return ""
    p = raw.strip().strip("'\"").strip()
    return os.path.abspath(os.path.expanduser(p))


def parse_timestamp(raw: str) -> float:
    """Parse various timestamp representations (HH:MM:SS, MM:SS, or seconds) into float seconds."""
    raw = (raw or "").strip()
    if not raw:
        return 0.0
    if ":" in raw:
        parts = [float(p) for p in raw.split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
    try:
        return float(raw)
    except ValueError:
        return 0.0


def format_timestamp(sec: float) -> str:
    """Format seconds into HH:MM:SS.ss string."""
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:05.2f}"
    return f"{m:02d}:{s:05.2f}"


def get_video_info(video_path: str) -> dict:
    """Retrieve video dimensions and duration via ffprobe."""
    try:
        cmd = [
            _find_tool("ffprobe"), "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-show_entries", "format=duration",
            "-of", "json",
            os.path.abspath(video_path),
        ]
        out = subprocess.check_output(cmd, text=True)
        data = json.loads(out)
        streams = data.get("streams", [])
        v = streams[0] if streams else {}
        fmt = data.get("format", {})
        dur = float(v.get("duration") or fmt.get("duration") or 0.0)
        return {
            "width": int(v.get("width", 0)),
            "height": int(v.get("height", 0)),
            "duration": dur,
        }
    except Exception:
        return {"width": 0, "height": 0, "duration": 0.0}


def scan_available_videos() -> list:
    """Scan assets/clips, D:\\Media\\movies, assets, and assets/output for video files."""
    extensions = (".mp4", ".mkv", ".mov", ".avi")
    found = []
    seen = set()

    search_dirs = [
        os.path.join(ASSETS_DIR, "clips"),
        r"D:\Media\movies",
        ASSETS_DIR,
        os.path.join(ASSETS_DIR, "output"),
    ]

    for folder in search_dirs:
        if not os.path.isdir(folder):
            continue
        # Limit scan depth to avoid long traversal
        for root, dirs, files in os.walk(folder):
            rel = os.path.relpath(root, folder)
            if rel.count(os.sep) > 2:
                dirs.clear()
                continue
            for f in files:
                if f.lower().endswith(extensions):
                    full_path = os.path.abspath(os.path.join(root, f))
                    if full_path not in seen and not f.startswith("."):
                        seen.add(full_path)
                        found.append(full_path)
    return found


def select_video_dialog(prompt_label: str = "Select a source video") -> str:
    """Interactive video selector listing known clips or accepting custom path."""
    videos = scan_available_videos()
    print(f"{Colors.BOLD}{prompt_label}:{Colors.RESET}\n")

    if videos:
        print(f"  {Colors.YELLOW}Detected video assets:{Colors.RESET}")
        for idx, vid in enumerate(videos[:15], 1):
            size_mb = os.path.getsize(vid) / (1024 * 1024)
            rel_name = os.path.relpath(vid, REPO_ROOT)
            print(f"    [{Colors.GREEN}{idx}{Colors.RESET}] {rel_name} ({size_mb:.1f} MB)")
        print()

    print(f"    [{Colors.GREEN}C{Colors.RESET}] Enter custom file path (or drag & drop video)")
    print(f"    [{Colors.RED}B{Colors.RESET}] Back to menu\n")

    while True:
        raw_choice = input(f"{Colors.CYAN}Selection > {Colors.RESET}").strip()
        choice = raw_choice.lower()
        if choice in ("b", "back", "0"):
            return None
        if choice == "c":
            raw = input(f"\n{Colors.CYAN}Enter full path to video file (or drag & drop): {Colors.RESET}")
            path = clean_input_path(raw)
            if os.path.isfile(path):
                return path
            print(f"{Colors.RED}File not found: '{path}'{Colors.RESET}\n")
            continue

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(videos[:15]):
                return videos[idx - 1]

        # Maybe user directly dragged and dropped or pasted a file path
        direct_path = clean_input_path(raw_choice)
        if os.path.isfile(direct_path):
            return direct_path

        print(f"{Colors.RED}Invalid option. Please select a number, 'C', or 'B' (or drag & drop video).{Colors.RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# Feature 1: Autonomous AI Clip Cutter (Top-N Viral Shorts)
# ─────────────────────────────────────────────────────────────────────────────

def menu_auto_clip_cutter():
    print_header("1. AUTONOMOUS AI TOP-N VIRAL SHORTS CUTTER")
    print(f"Extracts top viral scenes, crops to vertical 9:16 (YuNet), and burns karaoke subtitles.\n")

    video_path = select_video_dialog("Select Video to Cut into Viral Shorts")
    if not video_path:
        return

    print(f"\n{Colors.BOLD}Configuration for:{Colors.RESET} {os.path.basename(video_path)}")

    # Number of clips
    n_input = input(f"{Colors.CYAN}Number of clips to extract [default: 2]: {Colors.RESET}").strip()
    num_clips = int(n_input) if n_input.isdigit() and int(n_input) > 0 else 2

    # Min / Max duration
    min_input = input(f"{Colors.CYAN}Min duration in seconds [default: 15.0]: {Colors.RESET}").strip()
    min_dur = float(min_input) if min_input else 15.0

    max_input = input(f"{Colors.CYAN}Max duration in seconds [default: 45.0]: {Colors.RESET}").strip()
    max_dur = float(max_input) if max_input else 45.0

    # Whisper Model Size
    model_choice = input(f"{Colors.CYAN}Whisper model (tiny/base/small/medium) [default: base]: {Colors.RESET}").strip().lower()
    if model_choice not in ("tiny", "base", "small", "medium", "large"):
        model_choice = "base"

    # Upload option
    up_choice = input(f"{Colors.CYAN}Automatically upload/schedule to YouTube? (y/N) [default: n]: {Colors.RESET}").strip().lower()
    do_upload = up_choice in ("y", "yes")

    schedule_hrs = 24.0
    if do_upload:
        hrs_input = input(f"{Colors.CYAN}Hours between scheduled uploads [default: 24.0]: {Colors.RESET}").strip()
        if hrs_input:
            try:
                schedule_hrs = float(hrs_input)
            except ValueError:
                schedule_hrs = 24.0

    # Force re-render
    force_choice = input(f"{Colors.CYAN}Force fresh re-transcription & render? (y/N) [default: n]: {Colors.RESET}").strip().lower()
    do_force = force_choice in ("y", "yes")

    print(f"\n{Colors.GREEN}{Colors.BOLD}Starting Pipeline Execution...{Colors.RESET}\n")

    cmd = [
        sys.executable,
        os.path.join(SCRIPTS_DIR, "run_ai_cutter.py"),
        video_path,
        "-n", str(num_clips),
        "--min-duration", str(min_dur),
        "--max-duration", str(max_dur),
        "--model-size", model_choice,
    ]
    if do_upload:
        cmd.extend(["--upload", "--schedule-interval", str(schedule_hrs)])
    if do_force:
        cmd.append("--force")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n{Colors.RED}Pipeline exited with error: {e}{Colors.RESET}")
    pause()


# ─────────────────────────────────────────────────────────────────────────────
# Feature 2: Video Clip Cutter & Scene Extraction Studio
# ─────────────────────────────────────────────────────────────────────────────

def menu_cut_video_clips():
    print_header("2. CUT VIDEO CLIPS (FAST TRIM / 9:16 VERTICAL / BATCH)")
    print("Extract scenes from any video file with high-speed stream copy, 9:16 vertical reframe, or batch mode.\n")

    video_path = select_video_dialog("Select or Drag & Drop Video to Cut")
    if not video_path:
        return

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    slug = slugify(base_name)
    info = get_video_info(video_path)
    dur_str = format_timestamp(info["duration"]) if info["duration"] > 0 else "Unknown"
    res_str = f"{info['width']}x{info['height']}" if info['width'] > 0 else "Unknown"

    print(f"\n{Colors.BOLD}Selected Video:{Colors.RESET} {Colors.CYAN}{os.path.basename(video_path)}{Colors.RESET}")
    print(f"  Resolution: {res_str} | Total Duration: {dur_str} ({info['duration']:.1f}s)\n")

    print(f"{Colors.BOLD}Choose Cutting Mode:{Colors.RESET}")
    print(f"  [{Colors.GREEN}1{Colors.RESET}] Fast Lossless Cut (Instant stream-copy, original aspect ratio, zero re-encoding)")
    print(f"  [{Colors.CYAN}2{Colors.RESET}] AI Vertical 9:16 Subject Reframe (YuNet face-tracking speaker framing)")
    print(f"  [{Colors.YELLOW}3{Colors.RESET}] Standard 9:16 Center Crop (Fixed 1080x1920 center-cut)")
    print(f"  [{Colors.MAGENTA}4{Colors.RESET}] Full AI Viral Short (YuNet Crop + Whisper Karaoke Subtitles + Color Grade)")
    print(f"  [{Colors.BLUE}5{Colors.RESET}] Batch Multi-Clip Extractor (Extract multiple scenes from this video at once)")
    print(f"  [{Colors.RED}0{Colors.RESET}] Cancel\n")

    cut_mode = input(f"{Colors.CYAN}Select Mode [1-5] > {Colors.RESET}").strip()
    if cut_mode in ("0", "b", "back"):
        return

    clips_out_dir = os.path.join(ASSETS_DIR, "clips", slug)
    os.makedirs(clips_out_dir, exist_ok=True)

    # ── Mode 5: Batch Multi-Clip Extractor ───────────────────────────────────
    if cut_mode == "5":
        print(f"\n{Colors.BOLD}Batch Multi-Clip Extractor:{Colors.RESET}")
        print("Enter scene intervals in format 'start-end' or 'start duration'.")
        print("Example: '00:10:00-00:10:30, 01:25:00-01:25:45' or enter one per line.")
        batch_input = input(f"\n{Colors.CYAN}Enter intervals: {Colors.RESET}").strip()
        if not batch_input:
            print(f"{Colors.RED}No intervals provided.{Colors.RESET}")
            pause()
            return

        intervals = [item.strip() for item in batch_input.split(",") if item.strip()]
        rendered = []

        is_vertical = input(f"{Colors.CYAN}Apply 9:16 vertical reformatting to all batch clips? (y/N) [default: n]: {Colors.RESET}").strip().lower() in ("y", "yes")

        for idx, item in enumerate(intervals, 1):
            try:
                if "-" in item:
                    s_str, e_str = item.split("-", 1)
                    s_sec = parse_timestamp(s_str)
                    e_sec = parse_timestamp(e_str)
                    d_sec = max(1.0, e_sec - s_sec)
                else:
                    parts = item.split()
                    s_sec = parse_timestamp(parts[0])
                    d_sec = float(parts[1]) if len(parts) > 1 else 30.0

                out_file = os.path.join(clips_out_dir, f"clip_{idx:02d}_{int(s_sec)}s_{int(d_sec)}s.mp4")
                print(f"\nExtracting Scene #{idx}: {format_timestamp(s_sec)} for {d_sec:.1f}s -> {os.path.basename(out_file)}")

                if is_vertical:
                    crop_to_vertical(video_path, s_sec, d_sec, out_file)
                else:
                    cut_clip(video_path, start=str(s_sec), duration=str(d_sec), output_path=out_file, copy=True)

                rendered.append(out_file)
                print(f" {Colors.GREEN}Saved: {out_file}{Colors.RESET}")
            except Exception as ex:
                print(f"{Colors.RED}Error extracting '{item}': {ex}{Colors.RESET}")

        print(f"\n{Colors.GREEN}{Colors.BOLD}Batch extraction complete! Extracted {len(rendered)} clips to:{Colors.RESET}")
        print(f"  {clips_out_dir}")
        if os.name == "nt" and rendered:
            if input(f"\n{Colors.CYAN}Open destination folder in Explorer? (Y/n): {Colors.RESET}").strip().lower() not in ("n", "no"):
                os.startfile(clips_out_dir)
        pause()
        return

    # ── Single Clip Modes (1, 2, 3, 4) ───────────────────────────────────────
    start_raw = input(f"{Colors.CYAN}Start timestamp (e.g. 01:45:10, 45:10, or seconds) [default: 0]: {Colors.RESET}").strip()
    start_sec = parse_timestamp(start_raw)

    end_or_dur = input(f"{Colors.CYAN}Duration in seconds (e.g. 30) OR End timestamp (e.g. 01:45:40) [default: 30]: {Colors.RESET}").strip()
    if not end_or_dur:
        dur_sec = 30.0
    elif ":" in end_or_dur:
        end_sec = parse_timestamp(end_or_dur)
        dur_sec = max(1.0, end_sec - start_sec)
    else:
        try:
            dur_sec = float(end_or_dur)
        except ValueError:
            dur_sec = 30.0

    out_clip_name = f"{slug}_cut_{int(start_sec)}s_{int(dur_sec)}s.mp4"
    out_clip_path = os.path.join(ASSETS_DIR, "clips", out_clip_name)

    print(f"\n{Colors.GREEN}{Colors.BOLD}Processing Clip: {format_timestamp(start_sec)} -> {format_timestamp(start_sec + dur_sec)} ({dur_sec}s)...{Colors.RESET}\n")

    out_result = None
    try:
        if cut_mode == "1":
            # Fast Lossless Cut
            print("Applying lossless stream copy (0 re-encoding)...")
            out_result = cut_clip(video_path, start=str(start_sec), duration=str(dur_sec), output_path=out_clip_path, copy=True)

        elif cut_mode == "2":
            # AI Vertical 9:16 YuNet
            print("Analyzing face focal center with YuNet and reframing to 1080x1920...")
            out_result = crop_to_vertical(video_path, start_sec, dur_sec, out_clip_path)

        elif cut_mode == "3":
            # Standard 9:16 Center Crop
            print("Cropping center 1080x1920...")
            out_result = cut_clip(video_path, start=str(start_sec), duration=str(dur_sec), output_path=out_clip_path, vertical=True)

        elif cut_mode == "4":
            # Full AI Short with Subtitles
            print("Running full AI Short pipeline (Crop + Transcription + Kinetic Karaoke + Grade)...")
            final_short_path = os.path.join(ASSETS_DIR, "output", f"{slug}_short_{int(start_sec)}s.mp4")
            cmd = [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "run_ai_cutter.py"),
                video_path,
                "-s", str(start_sec),
                "-t", str(dur_sec),
            ]
            subprocess.run(cmd, check=True)
            out_result = final_short_path

        if out_result and os.path.isfile(out_result):
            print(f"\n{Colors.GREEN}{Colors.BOLD}SUCCESS! Clip saved to:{Colors.RESET}\n  {out_result}")
            if os.name == "nt":
                play = input(f"\n{Colors.CYAN}Play clip now in default media player? (Y/n) [default: y]: {Colors.RESET}").strip().lower()
                if play not in ("n", "no"):
                    os.startfile(out_result)
        else:
            print(f"{Colors.YELLOW}Clip created at {out_clip_path}{Colors.RESET}")
    except Exception as ex:
        print(f"\n{Colors.RED}Error processing clip: {ex}{Colors.RESET}")

    pause()


# Backward compatibility alias
menu_manual_cutter = menu_cut_video_clips


# ─────────────────────────────────────────────────────────────────────────────
# Feature 3: Movie Mystery Breakdown Shorts Engine
# ─────────────────────────────────────────────────────────────────────────────

def menu_mystery_engine():
    print_header("3. MOVIE MYSTERY BREAKDOWN SHORTS ENGINE")
    print(f"Generates 4-part open-loop mystery script, AI voiceover, and multi-clip assembly.\n")

    title = input(f"{Colors.CYAN}Movie Title (e.g. 'The Usual Suspects', 'Inception'): {Colors.RESET}").strip()
    if not title:
        print(f"{Colors.RED}Movie title is required.{Colors.RESET}")
        pause()
        return

    mode_choice = input(f"{Colors.CYAN}Formula mode (mystery / review) [default: mystery]: {Colors.RESET}").strip().lower()
    mode = "review" if mode_choice == "review" else "mystery"

    force_choice = input(f"{Colors.CYAN}Force fresh generation (bypass cache)? (y/N) [default: n]: {Colors.RESET}").strip().lower()
    force = force_choice in ("y", "yes")

    upload_choice = input(f"{Colors.CYAN}Upload completed Short to YouTube? (y/N) [default: n]: {Colors.RESET}").strip().lower()
    do_upload = upload_choice in ("y", "yes")

    print(f"\n{Colors.GREEN}{Colors.BOLD}Running Mystery Pipeline for '{title}'...{Colors.RESET}\n")

    cmd = [
        sys.executable,
        os.path.join(SCRIPTS_DIR, "run_pipeline.py"),
        title,
        "--mode", mode,
    ]
    if force:
        cmd.append("--force")
    if do_upload:
        cmd.append("--upload")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n{Colors.RED}Pipeline error: {e}{Colors.RESET}")
    pause()


# ─────────────────────────────────────────────────────────────────────────────
# Feature 4: Modular Tools & Utilities Sub-Menu
# ─────────────────────────────────────────────────────────────────────────────

def menu_modular_tools():
    while True:
        print_header("4. MODULAR TOOLS & UTILITIES")
        print("  [1] Transcribe Video (faster-whisper word timestamps)")
        print("  [2] Detect & Score Viral Moments (preview ranking & hook titles)")
        print("  [3] Vertical Reframe / Face Crop (YuNet 9:16 speaker tracking)")
        print("  [4] Burn Kinetic Karaoke Subtitles & Grade (.ass / .mp4)")
        print("  [5] Upload / Schedule Short to YouTube")
        print("  [0] Return to Main Menu\n")

        sub_choice = input(f"{Colors.CYAN}Select Tool > {Colors.RESET}").strip()
        if sub_choice in ("0", "b", "back", "exit"):
            break

        if sub_choice == "1":
            # Transcribe
            vid = select_video_dialog("Select Video to Transcribe")
            if vid:
                model = input(f"{Colors.CYAN}Whisper Model [default: base]: {Colors.RESET}").strip() or "base"
                print(f"\n{Colors.GREEN}Transcribing {vid}...{Colors.RESET}")
                t = transcribe_video(vid, model_size=model)
                slug = slugify(os.path.splitext(os.path.basename(vid))[0])
                print(f"\n{Colors.GREEN}Success! Transcript cached in assets/cache/{slug}_transcript.json{Colors.RESET}")
                print(f"Total duration: {t.get('duration')}s | Segments: {len(t.get('segments', []))}")
                pause()

        elif sub_choice == "2":
            # Detect Clips
            vid = select_video_dialog("Select Video to Detect Viral Moments")
            if vid:
                info = get_video_info(vid)
                dur = info.get("duration", 0)
                n_input = input(f"{Colors.CYAN}Top N clips [default: 3]: {Colors.RESET}").strip()
                top_n = int(n_input) if n_input.isdigit() else 3

                win_start = 0.0
                win_dur = None

                # Check if video is a full-length movie
                if dur > 900:  # > 15 minutes
                    print(f"\n{Colors.YELLOW}{Colors.BOLD}Notice:{Colors.RESET} Selected video is {dur/60:.1f} minutes long ({dur:.0f}s).")
                    print("Transcribing a full 2–3 hour movie on CPU typically takes 30–60+ minutes.")
                    print(f"  [{Colors.GREEN}1{Colors.RESET}] Fast-Scan: First 20 minutes (Instant hook detection in ~30s)")
                    print(f"  [{Colors.CYAN}2{Colors.RESET}] Custom Scene Window (Specify start timestamp & scan duration)")
                    print(f"  [{Colors.MAGENTA}3{Colors.RESET}] Full Movie Scan (Process all {dur/60:.0f} minutes of audio)")
                    print(f"  [{Colors.RED}0{Colors.RESET}] Cancel\n")

                    scan_opt = input(f"{Colors.CYAN}Select Scanning Mode [default: 1] > {Colors.RESET}").strip()
                    if scan_opt in ("0", "b", "back"):
                        continue
                    elif scan_opt == "2":
                        st_raw = input(f"{Colors.CYAN}Window start timestamp (e.g. 01:10:00 or 70:00) [default: 0]: {Colors.RESET}").strip()
                        win_start = parse_timestamp(st_raw)
                        win_dur_raw = input(f"{Colors.CYAN}Window duration in minutes [default: 15]: {Colors.RESET}").strip()
                        win_dur = float(win_dur_raw) * 60.0 if win_dur_raw else 900.0
                    elif scan_opt == "3":
                        win_start = 0.0
                        win_dur = None
                    else:
                        win_start = 0.0
                        win_dur = 1200.0  # 20 mins

                print(f"\n{Colors.GREEN}Analyzing viral moments...{Colors.RESET}")
                if win_dur is not None:
                    base = os.path.splitext(os.path.basename(vid))[0]
                    slug = slugify(base)
                    temp_wav = os.path.join(ASSETS_DIR, "audio", f"{slug}_win_{int(win_start)}s.wav")
                    ffmpeg_bin = _find_tool("ffmpeg")
                    print(f"Extracting {win_dur/60:.1f} min audio slice from {format_timestamp(win_start)}...")
                    cmd = [
                        ffmpeg_bin, "-y",
                        "-ss", str(win_start),
                        "-t", str(win_dur),
                        "-i", os.path.abspath(vid),
                        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                        temp_wav
                    ]
                    subprocess.run(cmd, check=True, capture_output=True)
                    from faster_whisper import WhisperModel
                    print(f"Scanning audio window with Whisper...")
                    model = WhisperModel("base", device="cpu", compute_type="int8")
                    segments_gen, _ = model.transcribe(temp_wav, word_timestamps=True)
                    segments_list = []
                    for seg in segments_gen:
                        words = [{"word": w.word, "start": w.start, "end": w.end} for w in (seg.words or [])]
                        segments_list.append({
                            "id": seg.id,
                            "start": seg.start,
                            "end": seg.end,
                            "text": seg.text.strip(),
                            "words": words,
                        })
                    win_transcript = {"segments": segments_list}
                    raw_clips = find_top_n_clips(win_transcript, temp_wav, top_n=top_n, min_duration=15.0, max_duration=55.0)
                    clips = []
                    for c in raw_clips:
                        c["start"] = round(c["start"] + win_start, 2)
                        c["end"] = round(c["end"] + win_start, 2)
                        clips.append(c)
                    try:
                        os.remove(temp_wav)
                    except OSError:
                        pass
                else:
                    clips = detect_clips(vid, top_n=top_n, min_duration=15.0, max_duration=55.0)

                print(f"\n--- Found {len(clips)} Top Moments ---")
                for c in clips:
                    print(f"  [Rank {c['rank']}] Score: {c['score']} | {format_timestamp(c['start'])} ({c['start']}s) -> {format_timestamp(c['end'])} ({c['end']}s) [Duration: {c['duration']}s]")
                    print(f"    Hook: \"{c.get('hook_title') or c.get('hook')}\"")
                pause()

        elif sub_choice == "3":
            # Face Crop / Framing
            vid = select_video_dialog("Select Video for Vertical Crop")
            if vid:
                info = get_video_info(vid)
                vw = info.get("width", 1920)
                vh = info.get("height", 1080)
                aspect = vw / max(vh, 1)

                print(f"\nVideo resolution: {vw}x{vh} (Aspect ratio: {aspect:.2f}:1)")
                if aspect > 2.0:
                    print(f"{Colors.YELLOW}Notice: CinemaScope widescreen detected ({aspect:.2f}:1).{Colors.RESET}")
                    print(f"Direct 9:16 crop will zoom in ~2.4x. Canvas Fit preserves full widescreen arms & landscape.")

                print("\nSelect Framing Mode:")
                print(f"  [{Colors.GREEN}1{Colors.RESET}] Smart 9:16 Reframe (Full vertical bleed with face tracking)")
                print(f"  [{Colors.CYAN}2{Colors.RESET}] Cinematic Canvas Fit (Full widescreen + blurred ambient background)")

                mode_opt = input(f"{Colors.CYAN}Framing Mode [default: 1] > {Colors.RESET}").strip()
                crop_mode = "canvas_blur" if mode_opt == "2" else "reframe"

                s = float(input(f"{Colors.CYAN}Start timestamp in seconds [default: 0]: {Colors.RESET}").strip() or "0")
                d = float(input(f"{Colors.CYAN}Duration in seconds [default: 30]: {Colors.RESET}").strip() or "30")
                base = os.path.splitext(os.path.basename(vid))[0]
                suffix = "canvas_9x16" if crop_mode == "canvas_blur" else "cropped_9x16"
                out = os.path.join(ASSETS_DIR, "clips", f"{base}_{suffix}.mp4")

                print(f"\n{Colors.GREEN}Rendering 9:16 vertical ({crop_mode})...{Colors.RESET}")
                res = crop_to_vertical(vid, s, d, out, mode=crop_mode)
                print(f"{Colors.GREEN}Saved to: {res}{Colors.RESET}")
                pause()

        elif sub_choice == "4":
            # Burn Subtitles
            vid = select_video_dialog("Select 9:16 Video Clip to Burn Subtitles Into")
            if vid:
                # Find matching transcript or ask
                base = os.path.splitext(os.path.basename(vid))[0]
                slug = slugify(base)
                default_json = os.path.join(ASSETS_DIR, "cache", f"{slug}_transcript.json")
                if not os.path.isfile(default_json):
                    json_cand = [f for f in os.listdir(os.path.join(ASSETS_DIR, "cache")) if f.endswith(".json")]
                    print(f"\nAvailable transcripts in cache:")
                    for idx, jf in enumerate(json_cand, 1):
                        print(f"  [{idx}] {jf}")
                    j_choice = input(f"{Colors.CYAN}Select transcript number or enter JSON path: {Colors.RESET}").strip()
                    if j_choice.isdigit() and 1 <= int(j_choice) <= len(json_cand):
                        t_path = os.path.join(ASSETS_DIR, "cache", json_cand[int(j_choice) - 1])
                    else:
                        t_path = clean_input_path(j_choice)
                else:
                    t_path = default_json

                if os.path.isfile(t_path):
                    print("\nSelect Subtitle Style:")
                    print(f"  [{Colors.GREEN}1{Colors.RESET}] Viral Shorts Standard (ALL-CAPS, Impact font, Neon Yellow/Green, 2-line stack) [Recommended]")
                    print(f"  [{Colors.CYAN}2{Colors.RESET}] Classic Minimal (Arial, yellow highlight, single line)")

                    style_opt = input(f"{Colors.CYAN}Subtitle Style [default: 1] > {Colors.RESET}").strip()
                    sub_style = "classic" if style_opt == "2" else "viral_shorts"

                    out_path = os.path.join(ASSETS_DIR, "output", f"{base}_viral_short.mp4")
                    print(f"\n{Colors.GREEN}Burning kinetic subtitles ({sub_style}) & applying cinematic grade...{Colors.RESET}")
                    res = burn_subtitles_and_grade(vid, t_path, out_path, style=sub_style)
                    print(f"{Colors.GREEN}Saved short to: {res}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}Transcript JSON not found.{Colors.RESET}")
                pause()

        elif sub_choice == "5":
            # Upload Video
            vid = select_video_dialog("Select Video Short to Upload")
            if vid:
                title = input(f"{Colors.CYAN}Shorts Title (e.g. 'Insane Plot Twist #shorts'): {Colors.RESET}").strip()
                desc = input(f"{Colors.CYAN}Description: {Colors.RESET}").strip() or "#shorts #movies"
                sched = input(f"{Colors.CYAN}Publish ISO UTC timestamp (or leave blank for public now): {Colors.RESET}").strip() or None
                print(f"\n{Colors.GREEN}Uploading to YouTube...{Colors.RESET}")
                from upload_video import upload_video
                upload_video(vid, title, desc, ["movies", "shorts"], sched)
                pause()


# ─────────────────────────────────────────────────────────────────────────────
# Feature 5: Gallery & Output Manager
# ─────────────────────────────────────────────────────────────────────────────

def menu_gallery():
    print_header("5. GALLERY & OUTPUT MANAGER")
    out_dir = os.path.join(ASSETS_DIR, "output")
    if not os.path.isdir(out_dir):
        print(f"{Colors.YELLOW}Output directory is empty.{Colors.RESET}")
        pause()
        return

    files = [f for f in os.listdir(out_dir) if f.lower().endswith(".mp4")]
    if not files:
        print(f"{Colors.YELLOW}No rendered shorts found in assets/output/.{Colors.RESET}")
        pause()
        return

    print(f"Found {len(files)} rendered Shorts in {Colors.BOLD}assets/output/{Colors.RESET}:\n")
    for idx, f in enumerate(files, 1):
        fp = os.path.join(out_dir, f)
        size_mb = os.path.getsize(fp) / (1024 * 1024)
        mtime = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M")
        print(f"  [{Colors.GREEN}{idx}{Colors.RESET}] {f} ({size_mb:.1f} MB, {mtime})")

    print(f"\n  [{Colors.CYAN}E{Colors.RESET}] Open output folder in Windows Explorer")
    print(f"  [{Colors.RED}0{Colors.RESET}] Return to main menu\n")

    choice = input(f"{Colors.CYAN}Selection > {Colors.RESET}").strip().lower()
    if choice in ("0", "b", "back"):
        return
    elif choice == "e":
        if os.name == "nt":
            os.startfile(out_dir)
        else:
            subprocess.run(["xdg-open", out_dir])
    elif choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(files):
            target_file = os.path.join(out_dir, files[idx - 1])
            print(f"\n{Colors.GREEN}Launching {files[idx - 1]} in default player...{Colors.RESET}")
            if os.name == "nt":
                os.startfile(target_file)
            else:
                subprocess.run(["xdg-open", target_file])
    pause()


# ─────────────────────────────────────────────────────────────────────────────
# Feature 6: Health Check & Configuration Status
# ─────────────────────────────────────────────────────────────────────────────

def menu_health_check():
    print_header("6. SYSTEM HEALTH & API CONFIGURATION CHECK")

    print(f"{Colors.BOLD}1. Core Media Binaries:{Colors.RESET}")
    ffmpeg_tool = _find_tool("ffmpeg")
    ffprobe_tool = _find_tool("ffprobe")
    print(f"   FFmpeg : {Colors.GREEN}{ffmpeg_tool}{Colors.RESET}")
    print(f"   FFprobe: {Colors.GREEN}{ffprobe_tool}{Colors.RESET}")

    print(f"\n{Colors.BOLD}2. Local Computer Vision Models:{Colors.RESET}")
    yunet_path = os.path.join(ASSETS_DIR, "models", "face_detection_yunet_2023mar.onnx")
    haar_path = os.path.join(ASSETS_DIR, "models", "haarcascade_frontalface_default.xml")
    print(f"   YuNet ONNX Model : {Colors.GREEN}Present ({os.path.getsize(yunet_path):,} bytes){Colors.RESET}" if os.path.isfile(yunet_path) else f"   YuNet: {Colors.RED}Missing{Colors.RESET}")
    print(f"   Haar Cascade XML : {Colors.GREEN}Present ({os.path.getsize(haar_path):,} bytes){Colors.RESET}" if os.path.isfile(haar_path) else f"   Haar : {Colors.RED}Missing{Colors.RESET}")

    det_name, _ = get_face_detector()
    print(f"   Active Detector  : {Colors.GREEN}{det_name.upper()}{Colors.RESET}")

    print(f"\n{Colors.BOLD}3. API & Service Credentials (config/.env):{Colors.RESET}")
    env_file = os.path.join(CONFIG_DIR, ".env")
    if os.path.isfile(env_file):
        print(f"   Local .env file  : {Colors.GREEN}Present (gitignored){Colors.RESET}")
        from dotenv import dotenv_values
        config = dotenv_values(env_file)

        # ElevenLabs
        el_key = config.get("ELEVENLABS_API_KEY", "")
        if el_key and not el_key.startswith("your_"):
            print(f"   ElevenLabs Key   : {Colors.GREEN}Configured (sk_...{el_key[-6:]}){Colors.RESET}")
            # Quick validation check
            try:
                import requests
                r = requests.get("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": el_key}, timeout=5)
                if r.status_code == 200:
                    n_v = len(r.json().get("voices", []))
                    print(f"     ElevenLabs API : {Colors.GREEN}Online & Valid ({n_v} voices available){Colors.RESET}")
                else:
                    print(f"     ElevenLabs API : {Colors.RED}Error HTTP {r.status_code}{Colors.RESET}")
            except Exception as e:
                print(f"     ElevenLabs API : {Colors.YELLOW}Network check timed out ({e}){Colors.RESET}")
        else:
            print(f"   ElevenLabs Key   : {Colors.YELLOW}Not set or placeholder{Colors.RESET}")

        # TMDB
        tmdb_key = config.get("TMDB_API_KEY", "")
        if tmdb_key and not tmdb_key.startswith("your_"):
            print(f"   TMDB API Key     : {Colors.GREEN}Configured (...{tmdb_key[-6:]}){Colors.RESET}")
        else:
            print(f"   TMDB API Key     : {Colors.YELLOW}Not set or placeholder{Colors.RESET}")

        # YouTube OAuth
        yt_secret = os.path.join(CONFIG_DIR, "client_secret.json")
        yt_token = os.path.join(CONFIG_DIR, "token.json")
        print(f"   YouTube Secret   : {Colors.GREEN}Present{Colors.RESET}" if os.path.isfile(yt_secret) else f"   YouTube Secret   : {Colors.YELLOW}Missing (config/client_secret.json){Colors.RESET}")
        print(f"   YouTube Token    : {Colors.GREEN}Authenticated (token.json){Colors.RESET}" if os.path.isfile(yt_token) else f"   YouTube Token    : {Colors.DIM}Not authenticated yet{Colors.RESET}")

    else:
        print(f"   Local .env file  : {Colors.RED}Missing (copy config/.env.example to config/.env){Colors.RESET}")

    pause()


# ─────────────────────────────────────────────────────────────────────────────
# Main Loop
# ─────────────────────────────────────────────────────────────────────────────

def main_menu():
    while True:
        print_header()
        print(f"  {Colors.BOLD}[1]{Colors.RESET} {Colors.GREEN}Auto-Extract Top Viral Shorts{Colors.RESET} (Autonomous Pipeline)")
        print(f"      -> Ingest long video, detect top moments, 9:16 YuNet crop & karaoke burn\n")

        print(f"  {Colors.BOLD}[2]{Colors.RESET} {Colors.CYAN}Cut Video Clips / Scene Extraction Studio{Colors.RESET} (Lossless / 9:16 / Batch)")
        print(f"      -> Cut new video: Instant lossless cut, YuNet 9:16 vertical crop, batch scenes, or AI short\n")

        print(f"  {Colors.BOLD}[3]{Colors.RESET} {Colors.YELLOW}Movie Mystery Breakdown Shorts Engine{Colors.RESET}")
        print(f"      -> AI Script breakdown + Voiceover (ElevenLabs/Edge) + Multi-clip / Poster\n")

        print(f"  {Colors.BOLD}[4]{Colors.RESET} {Colors.MAGENTA}Modular Tools & Utilities{Colors.RESET}")
        print(f"      -> Transcribe, Detect Moments, Face Crop, Burn Subtitles, YouTube Upload\n")

        print(f"  {Colors.BOLD}[5]{Colors.RESET} {Colors.BLUE}Gallery & Output Manager{Colors.RESET}")
        print(f"      -> Inspect, launch in player, and browse rendered shorts in assets/output/\n")

        print(f"  {Colors.BOLD}[6]{Colors.RESET} System Health & API Configuration Check")
        print(f"      -> Verify FFmpeg, YuNet ONNX, ElevenLabs API, TMDB, and YouTube OAuth\n")

        print(f"  {Colors.BOLD}[0]{Colors.RESET} Exit\n")

        choice = input(f"{Colors.CYAN}{Colors.BOLD}Select an option [0-6] > {Colors.RESET}").strip()

        if choice == "1":
            menu_auto_clip_cutter()
        elif choice == "2":
            menu_manual_cutter()
        elif choice == "3":
            menu_mystery_engine()
        elif choice == "4":
            menu_modular_tools()
        elif choice == "5":
            menu_gallery()
        elif choice == "6":
            menu_health_check()
        elif choice in ("0", "q", "exit", "quit"):
            print(f"\n{Colors.CYAN}Thank you for using Project Delta AI Shorts Studio! Goodbye.{Colors.RESET}\n")
            sys.exit(0)
        else:
            print(f"{Colors.RED}Invalid choice. Please select 0 to 6.{Colors.RESET}")


if __name__ == "__main__":
    try:
        main_menu()
    except (KeyboardInterrupt, EOFError):
        print(f"\n\n{Colors.CYAN}Exiting... Goodbye!{Colors.RESET}")
        sys.exit(0)
