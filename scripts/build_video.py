"""
Builds high-retention 9:16 vertical videos from:
  1. Multi-clip assembly (build_multi_clip_video):
     - Concat demuxer (inputs.txt) of 3–5 scene clips
     - Cinematic color grading filter (contrast/saturation/brightness)
     - Burned-in ASS captions with yellow keyword highlights & safe margins
  2. Single poster Ken Burns slideshow (build_video):
     - Backward-compatible fallback when no footage clips are provided

Requires ffmpeg installed and on PATH (with WinGet fallback).
"""

import os
import re
import subprocess
import sys

# ── Caption styling constants ─────────────────────────────────────────────────

# ASS color format is &HAABBGGRR (alpha, blue, green, red).
# Yellow  (R=255 G=255 B=0)  → BGR 00FFFF → &H00FFFF&  (fully opaque yellow)
# White   (R=G=B=255)        → BGR FFFFFF → &H00FFFFFF& (fully opaque white)
_HIGHLIGHT = "&H00FFFF&"   # yellow — emphasis words
_BASE      = "&H00FFFFFF&" # white  — normal words

# Words that get highlighted when they appear in a caption chunk.
_PUNCH_WORDS = {
    "never", "actually", "real", "really", "best", "worst", "must", "only",
    "every", "always", "incredible", "amazing", "perfect", "insane", "wild",
    "genius", "brilliant", "stunning", "terrifying", "haunting", "extraordinary",
    "masterpiece", "underrated", "greatest", "trust", "stop", "earned", "rated",
    "impossible", "mind-bending", "mind", "bending", "ring", "truth", "clue",
    "secret", "mystery", "answer", "twist", "bare", "gone", "dream",
}


# ── Tool resolver (handles winget PATH-not-yet-refreshed) ────────────────────

_WINGET_LINKS = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\WinGet\Links"
)


def _find_tool(name: str) -> str:
    """
    Return the command to invoke name (e.g. 'ffprobe', 'ffmpeg').
    Checks PATH first; falls back to WinGet symlink directory.
    """
    import shutil
    if shutil.which(name):
        return name
    candidate = os.path.join(_WINGET_LINKS, f"{name}.exe")
    if os.path.exists(candidate):
        return candidate
    return name


# ── Audio and Video duration ──────────────────────────────────────────────────

def get_audio_duration(audio_path: str) -> float:
    result = subprocess.run(
        [
            _find_tool("ffprobe"), "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path,
        ],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def get_media_duration(path: str) -> float:
    try:
        result = subprocess.run(
            [
                _find_tool("ffprobe"), "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path,
            ],
            capture_output=True, text=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


# ── Smart caption chunking ────────────────────────────────────────────────────

def _smart_chunks(script_text: str, max_words: int = 6) -> list:
    """
    Split script into caption chunks at natural pause points.
    Priority: sentence punctuation -> clause punctuation -> word-count ceiling.
    """
    sentences = re.split(r'(?<=[.!?])\s+', script_text.strip())

    chunks = []
    for sentence in sentences:
        clauses = re.split(r'(?<=[,;:])\s+|(?<=\u2014)\s*|(?<= - )\s*', sentence)
        clauses = [c.strip() for c in clauses if c.strip()]

        pending = []
        for clause in clauses:
            words = clause.split()
            if not words:
                continue

            if pending and len(pending) + len(words) > max_words:
                chunks.append(" ".join(pending))
                pending = []

            if len(words) > max_words:
                if pending:
                    chunks.append(" ".join(pending))
                    pending = []
                for i in range(0, len(words), max_words):
                    chunks.append(" ".join(words[i : i + max_words]))
            else:
                pending.extend(words)

        if pending:
            chunks.append(" ".join(pending))

    return [c for c in chunks if c]


# ── Keyword highlighting ──────────────────────────────────────────────────────

def _highlight(text: str) -> str:
    """Wrap up to 2 punch words or numbers per chunk in yellow ASS tags."""
    words = text.split()
    result = []
    count = 0

    for word in words:
        bare = re.sub(r"[^a-zA-Z0-9.]", "", word).lower()
        is_number = bool(re.match(r"^\d+\.?\d*$", bare))
        is_punch  = bare in _PUNCH_WORDS

        if count < 2 and (is_number or is_punch):
            result.append(f"{{\\c{_HIGHLIGHT}}}{word}{{\\c{_BASE}}}")
            count += 1
        else:
            result.append(word)

    return " ".join(result)


# ── ASS subtitle builder ──────────────────────────────────────────────────────

def _ass_time(t: float) -> str:
    """Format seconds as ASS timestamp: H:MM:SS.cc (centiseconds)."""
    h  = int(t // 3600)
    m  = int((t % 3600) // 60)
    s  = t % 60
    cs = int((s - int(s)) * 100)
    return f"{h}:{m:02d}:{int(s):02d}.{cs:02d}"


def build_ass(script_text: str, duration: float, out_ass: str) -> None:
    """
    Generate an ASS subtitle file with smart chunking, yellow keyword highlights,
    and a safe bottom margin (MarginV=240) to avoid YouTube Shorts UI overlap.
    """
    chunks    = _smart_chunks(script_text)
    n         = len(chunks)
    per_chunk = duration / max(n, 1)

    # MarginV=240 lifts captions ~12.5% above bottom, clearing Shorts UI overlay
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "WrapStyle: 0\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        "-1,0,0,0,100,100,0,0,1,3,1,2,40,40,240,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, "
        "MarginL, MarginR, MarginV, Effect, Text\n"
    )

    with open(out_ass, "w", encoding="utf-8") as f:
        f.write(header)
        for i, chunk in enumerate(chunks):
            start = i * per_chunk
            end   = start + per_chunk
            styled = _highlight(chunk)
            f.write(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},"
                f"Default,,0,0,0,,{styled}\n"
            )


def load_words_from_transcript(transcript_source) -> list:
    """
    Extract a flat list of {'word': str, 'start': float, 'end': float}
    from a JSON file path, dict, or list of words.
    """
    import json
    if isinstance(transcript_source, str) and os.path.isfile(transcript_source):
        with open(transcript_source, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif isinstance(transcript_source, (dict, list)):
        data = transcript_source
    else:
        return []

    if isinstance(data, list):
        return data

    words = []
    if isinstance(data, dict):
        if "words" in data and isinstance(data["words"], list):
            return data["words"]
        for seg in data.get("segments", []):
            for w in seg.get("words", []):
                words.append({
                    "word": w.get("word", "").strip(),
                    "start": float(w.get("start", 0.0)),
                    "end": float(w.get("end", 0.0)),
                })
    return words


def build_karaoke_ass(
    words: list,
    out_ass_path: str,
    min_chunk_words: int = 3,
    max_chunk_words: int = 4,
) -> None:
    """
    Generate kinetic ASS subtitles with active word-by-word yellow karaoke highlighting.
    words: list of dicts with keys 'word', 'start', 'end' (or transcript JSON path).
    - Chunks word streams into 3-4 words per line.
    - Font size: FontSize=80 (~8% of 1920 vertical height).
    - Base color: fully opaque white (&H00FFFFFF&).
    - Highlight color: vibrant yellow (&H00FFFF&).
    - Safe margin: MarginV=240 (bottom safe margin avoiding Shorts UI).
    """
    if isinstance(words, (str, dict)):
        words = load_words_from_transcript(words)

    if not words:
        return

    # Clean words and filter valid timestamps
    valid_words = []
    for w in words:
        txt = w.get("word", "").strip()
        if txt and "start" in w and "end" in w:
            valid_words.append({
                "word": txt,
                "start": max(0.0, float(w["start"])),
                "end": max(float(w["end"]), float(w["start"]) + 0.05),
            })

    if not valid_words:
        return

    # Chunk into 3-4 word phrases, breaking on sentence ends or max chunk limit
    chunks = []
    current_chunk = []

    for w in valid_words:
        current_chunk.append(w)
        ends_sentence = any(w["word"].endswith(p) for p in (".", "!", "?"))
        if len(current_chunk) >= max_chunk_words or (len(current_chunk) >= min_chunk_words and ends_sentence):
            chunks.append(current_chunk)
            current_chunk = []

    if current_chunk:
        chunks.append(current_chunk)

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "WrapStyle: 0\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,80,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        "-1,0,0,0,100,100,0,0,1,3,1,2,40,40,240,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, "
        "MarginL, MarginR, MarginV, Effect, Text\n"
    )

    with open(out_ass_path, "w", encoding="utf-8") as f:
        f.write(header)

        for chunk in chunks:
            # For each word in the chunk, generate an active highlight event
            for idx, active_word in enumerate(chunk):
                w_start = active_word["start"]
                # Extend active highlight until the next word starts to prevent flickering
                if idx + 1 < len(chunk):
                    w_end = max(w_start + 0.05, chunk[idx + 1]["start"])
                else:
                    w_end = max(w_start + 0.05, active_word["end"])

                # Build line where active_word is yellow (&H00FFFF&) and others are white (&H00FFFFFF&)
                line_parts = []
                for j, w in enumerate(chunk):
                    w_text = w["word"]
                    if j == idx:
                        line_parts.append(f"{{\\c{_HIGHLIGHT}}}{w_text}{{\\c{_BASE}}}")
                    else:
                        line_parts.append(w_text)

                line_text = " ".join(line_parts)
                f.write(
                    f"Dialogue: 0,{_ass_time(w_start)},{_ass_time(w_end)},"
                    f"Default,,0,0,0,,{line_text}\n"
                )


# Alias for backward compatibility
build_kinetic_ass = build_karaoke_ass


def burn_subtitles_and_grade(
    video_path: str,
    words_data: list,
    out_path: str = None,
    start_time: float = None,
    duration: float = None,
) -> str:
    """
    Burn kinetic subtitles and cinematic color grading into a 9:16 vertical clip.
    Applies unified filtergraph:
      -vf "eq=contrast=1.12:saturation=1.15:brightness=-0.02,subtitles=<ass_filename>"
    Executed inside the subtitle directory to avoid Windows drive-letter escaping issues.
    """
    if isinstance(words_data, (str, dict)):
        words_data = load_words_from_transcript(words_data)

    # If start_time is specified, slice words to relative timestamps
    if start_time is not None and start_time > 0:
        end_time = (start_time + duration) if duration else float("inf")
        filtered_words = []
        for w in words_data:
            ws = float(w["start"])
            we = float(w["end"])
            if ws >= start_time - 0.2 and we <= end_time + 0.5:
                rel_start = max(0.0, round(ws - start_time, 3))
                rel_end = max(rel_start + 0.05, round(we - start_time, 3))
                filtered_words.append({
                    "word": w["word"],
                    "start": rel_start,
                    "end": rel_end,
                })
        words_data = filtered_words

    if not out_path:
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "output"))
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{base_name}_short_01.mp4")

    out_abs = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)

    ass_path = out_abs.replace(".mp4", ".ass")
    build_karaoke_ass(words_data, ass_path)

    ass_dir = os.path.dirname(ass_path)
    ass_name = os.path.basename(ass_path)

    # Check input dimensions
    probe_cmd = [
        _find_tool("ffprobe"), "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        os.path.abspath(video_path),
    ]
    try:
        dim = subprocess.check_output(probe_cmd, text=True).strip().split("x")
        w, h = int(dim[0]), int(dim[1])
    except Exception:
        w, h = 1080, 1920

    if w == 1080 and h == 1920:
        vf = f"eq=contrast=1.12:saturation=1.15:brightness=-0.02,subtitles={ass_name}"
    else:
        vf = (
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"eq=contrast=1.12:saturation=1.15:brightness=-0.02,"
            f"subtitles={ass_name}"
        )

    cmd = [_find_tool("ffmpeg"), "-y"]
    if start_time is not None and start_time > 0:
        cmd.extend(["-ss", str(start_time)])
    cmd.extend(["-i", os.path.abspath(video_path)])
    if duration is not None:
        cmd.extend(["-t", str(duration)])

    cmd.extend([
        "-vf", vf,
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        out_abs,
    ])

    subprocess.run(cmd, check=True, cwd=ass_dir)
    print(f"Burned subtitles and applied cinematic grade to: {out_abs}")
    return out_abs


# Backward compatibility alias
build_short_from_clip = burn_subtitles_and_grade


# ── Multi-Clip Video Builder ──────────────────────────────────────────────────

def build_multi_clip_video(
    clips: list,
    audio_path: str,
    script_text: str,
    out_path: str,
) -> str:
    """
    Assemble an ordered list of 3–5 scene clips into a high-retention 9:16 Short.

    Applies:
      - FFmpeg concat demuxer (inputs.txt)
      - Standardized 1080x1920 scale/crop
      - Cinematic grade filter: eq=contrast=1.12:saturation=1.15:brightness=-0.02
      - Burned-in ASS subtitles with safe margins (MarginV=240)
      - Exact audio duration sync (-t duration -shortest)
    """
    if not clips:
        raise ValueError("build_multi_clip_video requires at least one clip path.")

    # Validate that all clip files exist
    valid_clips = []
    for c in clips:
        abs_c = os.path.abspath(c)
        if not os.path.isfile(abs_c):
            raise FileNotFoundError(f"Clip not found: {abs_c}")
        valid_clips.append(abs_c)

    duration = get_audio_duration(audio_path)
    out_abs = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)

    ass_path = out_abs.replace(".mp4", ".ass")
    build_ass(script_text, duration, ass_path)

    ass_dir = os.path.dirname(ass_path)
    ass_name = os.path.basename(ass_path)

    # Check total duration of provided clips; repeat list if shorter than voiceover
    total_clip_len = sum(get_media_duration(c) for c in valid_clips)
    playlist = list(valid_clips)
    if total_clip_len > 0 and total_clip_len < duration:
        repeats = int(duration // total_clip_len) + 1
        playlist = valid_clips * repeats

    # Write concat manifest
    manifest_path = out_abs.replace(".mp4", "_inputs.txt")
    with open(manifest_path, "w", encoding="utf-8") as f:
        for clip in playlist:
            # Concat demuxer requires forward slashes on Windows
            norm = clip.replace("\\", "/")
            f.write(f"file '{norm}'\n")

    # Unified video filter:
    # 1. scale+crop to 1080x1920
    # 2. cinematic color grade (contrast 1.12, saturation 1.15, brightness -0.02)
    # 3. subtitles with safe margins
    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,"
        f"eq=contrast=1.12:saturation=1.15:brightness=-0.02,"
        f"subtitles={ass_name}"
    )

    cmd = [
        _find_tool("ffmpeg"), "-y",
        "-f", "concat", "-safe", "0", "-i", os.path.abspath(manifest_path),
        "-i", os.path.abspath(audio_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(duration),
        "-shortest",
        out_abs,
    ]

    subprocess.run(cmd, check=True, cwd=ass_dir)

    # Clean up temporary manifest
    try:
        os.remove(manifest_path)
    except OSError:
        pass

    return out_abs


# ── Single Poster Fallback (Backward Compatibility) ───────────────────────────

def build_video(
    poster_path: str,
    audio_path: str,
    script_text: str,
    out_path: str,
) -> str:
    """
    Fallback video builder: generates a 9:16 vertical video from a static poster
    using Ken Burns pan/zoom and burned-in ASS captions.
    """
    duration = get_audio_duration(audio_path)
    out_abs = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)

    ass_path = out_abs.replace(".mp4", ".ass")
    build_ass(script_text, duration, ass_path)

    poster_abs = os.path.abspath(poster_path)
    audio_abs  = os.path.abspath(audio_path)
    ass_dir    = os.path.dirname(ass_path)
    ass_name   = os.path.basename(ass_path)

    zoom_frames = int(duration * 25)

    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,"
        f"zoompan="
        f"z='min(zoom+0.0005,1.10)':"
        f"x='(iw-iw/zoom)/2':"
        f"y='(ih-ih/zoom)/2':"
        f"d={zoom_frames}:s=1080x1920:fps=25,"
        f"eq=contrast=1.12:saturation=1.15:brightness=-0.02,"
        f"subtitles={ass_name}"
    )

    cmd = [
        _find_tool("ffmpeg"), "-y",
        "-loop", "1", "-i", poster_abs,
        "-i", audio_abs,
        "-vf", vf,
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        out_abs,
    ]
    subprocess.run(cmd, check=True, cwd=ass_dir)
    return out_abs


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("  Burn Karaoke Subtitles: python build_video.py <clip.mp4> <transcript.json> [out.mp4]")
        print("  Poster Ken Burns      : python build_video.py poster.jpg audio.mp3 \"script\" out.mp4")
        print("  Multi-clip Concat     : python build_video.py clip1.mp4,clip2.mp4 audio.mp3 \"script\" out.mp4")
        sys.exit(1)

    first_arg = sys.argv[1]
    second_arg = sys.argv[2]

    # Mode 1: Burn subtitles and color grade from transcript JSON
    if len(sys.argv) == 3 or (len(sys.argv) == 4 and second_arg.lower().endswith((".json", ".ass"))):
        out_arg = sys.argv[3] if len(sys.argv) > 3 else None
        res = burn_subtitles_and_grade(first_arg, second_arg, out_arg)
        print(f"Rendered short to {res}")
        sys.exit(0)

    # Mode 2 & 3: Multi-clip demuxer or poster fallback
    if len(sys.argv) >= 5:
        audio_arg = sys.argv[2]
        script_arg = sys.argv[3]
        out_arg = sys.argv[4]

        if "," in first_arg:
            clip_list = [c.strip() for c in first_arg.split(",")]
            build_multi_clip_video(clip_list, audio_arg, script_arg, out_arg)
        else:
            build_video(first_arg, audio_arg, script_arg, out_arg)
        print(f"Saved video to {out_arg}")
        sys.exit(0)
