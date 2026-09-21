"""
Local Word-Level Audio Transcription using faster-whisper.

Extracts audio from video to 16kHz mono WAV and generates word-level
timestamps cached to assets/cache/<slug>_transcript.json.
"""

import argparse
import json
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


# ── Audio Extraction ──────────────────────────────────────────────────────────

def extract_audio(video_path: str, out_wav_path: str) -> str:
    """Extract audio from video to 16kHz mono WAV for Whisper."""
    ffmpeg_bin = _find_tool("ffmpeg")
    os.makedirs(os.path.dirname(os.path.abspath(out_wav_path)), exist_ok=True)

    cmd = [
        ffmpeg_bin, "-y",
        "-i", os.path.abspath(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        os.path.abspath(out_wav_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_wav_path


# ── Transcription Engine ──────────────────────────────────────────────────────

def transcribe_video(
    video_path: str,
    model_size: str = "base",
    force: bool = False,
    device: str = "auto",
) -> dict:
    """
    Transcribe video using faster-whisper with word-level timestamps.
    Caches result to assets/cache/<slug>_transcript.json.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: '{video_path}'")

    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    cache_dir = os.path.join(assets_dir, "cache")
    audio_dir = os.path.join(assets_dir, "audio")
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    slug = slugify(base_name)
    cache_file = os.path.join(cache_dir, f"{slug}_transcript.json")

    # Check cache
    if not force and os.path.isfile(cache_file) and os.path.getsize(cache_file) > 0:
        print(f"[cached] Loading transcript from {cache_file}")
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Extract audio
    wav_path = os.path.join(audio_dir, f"{slug}_16k.wav")
    print(f"Extracting 16kHz audio from {video_path}...")
    extract_audio(video_path, wav_path)

    print(f"Loading faster-whisper model ('{model_size}')...")
    from faster_whisper import WhisperModel

    # Detect device (cuda or cpu)
    if device == "auto":
        try:
            import torch
            device_choice = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device_choice = "cpu"
    else:
        device_choice = device

    compute_type = "float16" if device_choice == "cuda" else "int8"
    print(f"Running on {device_choice.upper()} (compute_type={compute_type})...")

    import os
    cpu_cores = os.cpu_count() or 4
    threads = min(cpu_cores, 8) if device_choice == "cpu" else 4

    model = WhisperModel(model_size, device=device_choice, compute_type=compute_type, cpu_threads=threads)
    segments_gen, info = model.transcribe(
        wav_path,
        word_timestamps=True,
        beam_size=1,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=400),
    )

    total_dur = round(info.duration, 2)
    dur_min = int(total_dur // 60)
    dur_sec = int(total_dur % 60)
    print(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
    print(f"Total audio duration: {dur_min}m {dur_sec}s ({total_dur:.1f}s). Transcribing in progress...")
    sys.stdout.flush()

    segments_data = []
    full_text_parts = []
    last_reported_time = 0.0

    for seg in segments_gen:
        full_text_parts.append(seg.text.strip())
        words_data = []
        if seg.words:
            for w in seg.words:
                words_data.append({
                    "word": w.word,
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "probability": round(w.probability, 3),
                })

        segments_data.append({
            "id": seg.id,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
            "words": words_data,
        })

        # Print progress every ~15 seconds of audio or when significant text is spoken
        if seg.end - last_reported_time >= 15.0 or seg.id % 10 == 0:
            pct = min(100.0, (seg.end / max(1.0, total_dur)) * 100.0)
            cur_m = int(seg.end // 60)
            cur_s = int(seg.end % 60)
            snippet = seg.text.strip().replace("\n", " ")[:50]
            print(f"  [{pct:5.1f}% | {cur_m:02d}m{cur_s:02d}s / {dur_min:02d}m{dur_sec:02d}s] \"{snippet}\"")
            sys.stdout.flush()
            last_reported_time = seg.end

    result = {
        "source": os.path.abspath(video_path),
        "language": info.language,
        "duration": round(info.duration, 2),
        "text": " ".join(full_text_parts),
        "segments": segments_data,
    }

    # Save cache
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved transcript ({len(segments_data)} segments) to {cache_file}")

    # Remove temporary wav
    try:
        os.remove(wav_path)
    except OSError:
        pass

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Local word-level video transcription using faster-whisper."
    )
    parser.add_argument("video", help="Path to input video file")
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached transcript and rerun transcription",
    )
    args = parser.parse_args()

    try:
        data = transcribe_video(args.video, model_size=args.model, force=args.force)
        print("\n--- Transcription Summary ---")
        print(f"Language: {data.get('language')}")
        print(f"Duration: {data.get('duration')}s")
        print(f"Segments: {len(data.get('segments', []))}")
        print(f"Preview : {data.get('text')[:200]}...")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
