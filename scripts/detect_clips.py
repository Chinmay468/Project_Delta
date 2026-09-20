"""
Intelligent Clip Detection from Word-Level Transcripts.

Scores and extracts high-retention 30–60s moments based on:
  - Sentence & clause completeness (snapping to silence pauses)
  - Hook strength (questions, dramatic declarations, punch words)
  - Information density & speech cadence (120–170 wpm)
"""

import argparse
import json
import os
import re
import sys

from transcribe import transcribe_video, slugify

_PUNCH_WORDS = {
    "who", "what", "why", "how", "never", "actually", "real", "really",
    "dead", "murder", "murderer", "killer", "secret", "truth", "clue",
    "impossible", "insane", "greatest", "trick", "devil", "twist",
    "know", "believe", "listen", "remember", "look", "gun", "money",
    "soze", "keyser", "cobb", "cop", "police", "game", "die", "death",
    "mystery", "nobody", "everybody", "always", "lies", "lie", "lied",
}
_HOOK_PUNCH_WORDS = _PUNCH_WORDS  # Alias for backward compatibility


def _score_segment(text: str, duration: float, words_count: int) -> float:
    """Calculate retention score for a text segment based on Q&A and punch words."""
    if duration <= 0:
        return 0.0

    score = 5.0
    lower = text.lower()

    # 1. Question-and-Answer (Q&A) pattern (+2.5 to +3.5)
    if "?" in text:
        parts = text.split("?")
        if len(parts) > 1 and len(parts[1].strip().split()) >= 3:
            score += 3.5  # Question asked early followed by substantive answer/dialogue
        else:
            score += 2.0  # Standalone question hook

    # 2. Punch word density from _PUNCH_WORDS (+0.5 per punch word, max +4.0)
    words = re.findall(r"\b[a-zA-Z]+\b", lower)
    punch_count = sum(1 for w in words if w in _PUNCH_WORDS)
    score += min(punch_count * 0.5, 4.0)

    # 3. Speech cadence penalty/reward (optimal: 120-170 wpm)
    wpm = (words_count / duration) * 60
    if 120 <= wpm <= 170:
        score += 1.5
    elif wpm < 80 or wpm > 220:
        score -= 2.0

    # 4. Clean sentence start / exclamation (+1.0)
    if text.endswith((".", "!", "?")):
        score += 1.0

    return round(score, 2)


def detect_clips(
    video_path: str,
    transcript: dict = None,
    min_duration: float = 30.0,
    max_duration: float = 60.0,
    top_n: int = 3,
) -> list:
    """
    Scan transcript segments for 30–60s clips, snapping to silence gaps (>0.4s)
    and sentence ends to prevent audio clipping.
    """
    if transcript is None:
        transcript = transcribe_video(video_path)

    segments = transcript.get("segments", [])
    if not segments:
        return []

    candidates = []

    # Slide over segments to form complete sentences totaling min_duration to max_duration
    for i in range(len(segments)):
        # Check start boundary: snap to silence gaps (>0.4s) or clean sentence start
        start_time = segments[i]["start"]
        is_clean_start = False
        if i == 0:
            is_clean_start = True
        else:
            pause_before = start_time - segments[i - 1]["end"]
            prev_ended = any(segments[i - 1]["text"].strip().endswith(p) for p in (".", "!", "?"))
            if pause_before >= 0.4 or prev_ended:
                is_clean_start = True

        current_text_parts = []
        words_in_window = 0

        for j in range(i, len(segments)):
            seg = segments[j]
            end_time = seg["end"]
            dur = end_time - start_time

            current_text_parts.append(seg["text"].strip())
            words_in_window += len(seg.get("words", [])) or len(seg["text"].split())

            if dur >= min_duration:
                if dur <= max_duration:
                    # Check end boundary: snap to sentence end or silence gap (>0.4s)
                    is_clean_end = False
                    ends_with_punc = any(seg["text"].strip().endswith(p) for p in (".", "!", "?"))
                    if ends_with_punc:
                        is_clean_end = True
                    elif j + 1 < len(segments):
                        pause_after = segments[j + 1]["start"] - end_time
                        if pause_after >= 0.4:
                            is_clean_end = True
                    elif j == len(segments) - 1:
                        is_clean_end = True

                    text_block = " ".join(current_text_parts)
                    score = _score_segment(text_block, dur, words_in_window)
                    if is_clean_start and is_clean_end:
                        score += 1.5  # High priority for cleanly snapped audio boundaries

                    # Extract the hook (first sentence or first 12 words)
                    first_sentence = re.split(r'(?<=[.!?])\s+', text_block)[0]
                    hook = first_sentence if len(first_sentence.split()) <= 15 else " ".join(first_sentence.split()[:12]) + "..."

                    candidates.append({
                        "start": round(start_time, 2),
                        "end": round(end_time, 2),
                        "duration": round(dur, 2),
                        "score": score,
                        "hook": hook,
                        "text": text_block,
                        "clean_boundary": is_clean_start and is_clean_end,
                        "start_segment_id": segments[i].get("id", i),
                        "end_segment_id": seg.get("id", j),
                    })
                else:
                    break

    # If no window met the exact min/max bounds (e.g. video is under min_duration),
    # use the entire video duration as a single candidate
    if not candidates and segments:
        full_dur = segments[-1]["end"] - segments[0]["start"]
        candidates.append({
            "start": round(segments[0]["start"], 2),
            "end": round(segments[-1]["end"], 2),
            "duration": round(full_dur, 2),
            "score": 8.0,
            "hook": segments[0]["text"][:60],
            "text": transcript.get("text", ""),
            "start_segment_id": segments[0].get("id", 0),
            "end_segment_id": segments[-1].get("id", len(segments) - 1),
        })

    # Deduplicate overlapping candidates (keep highest score)
    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = []

    for cand in candidates:
        overlap = False
        for s in selected:
            # Check if intervals overlap significantly (> 40% duration)
            ov_start = max(cand["start"], s["start"])
            ov_end = min(cand["end"], s["end"])
            if ov_end > ov_start:
                ov_len = ov_end - ov_start
                if ov_len / min(cand["duration"], s["duration"]) > 0.4:
                    overlap = True
                    break
        if not overlap:
            selected.append(cand)
            if len(selected) >= top_n:
                break

    for rank, item in enumerate(selected, 1):
        item["rank"] = rank

    return selected


def main():
    parser = argparse.ArgumentParser(
        description="Detect high-retention 30–60s moments from video transcripts."
    )
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--top", type=int, default=3, help="Number of top clips to return (default: 3)")
    parser.add_argument("--min-dur", type=float, default=20.0, help="Min duration in seconds (default: 20)")
    parser.add_argument("--max-dur", type=float, default=60.0, help="Max duration in seconds (default: 60)")
    args = parser.parse_args()

    try:
        clips = detect_clips(
            args.video,
            min_duration=args.min_dur,
            max_duration=args.max_dur,
            top_n=args.top,
        )

        print(f"\n--- Detected Top {len(clips)} Moments for '{os.path.basename(args.video)}' ---")
        for c in clips:
            print(f"\n[Rank {c['rank']}] Score: {c['score']}/10  |  Duration: {c['duration']}s ({c['start']}s -> {c['end']}s)")
            print(f"Hook: \"{c['hook']}\"")
            print(f"Text: \"{c['text'][:120]}...\"")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
