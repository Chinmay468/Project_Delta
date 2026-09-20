"""
High-Retention Movie Mystery Shorts Script Generator.

Generates 20–28s spoken voiceover scripts (~50–75 words) using the
Open-Loop Mystery Breakdown formula:
  1. The Hook (0:00–0:05, 10–15 words): Pose an unresolved ending or ambiguous detail.
  2. The Authority Pivot (0:05–0:08, 10–15 words): Introduce directorial intent or proof.
  3. The Perspective Shift (0:08–0:16, 20–30 words): Deliver the core revelation/payoff.
  4. The Visual Loop (0:16–0:22, 10–15 words): Re-ask premise & tie back to opening shot.

Supports both curated cinematic mysteries and dynamic procedural generation.
"""

import argparse
import random
import re
import sys

_MIN_WORDS = 50
_MAX_WORDS = 75

# ── Curated Mystery Presets ───────────────────────────────────────────────────

_CURATED_MYSTERIES = {
    "inception": {
        "hook": "Did Cobb actually escape the dream at the end of Inception?",
        "pivot": "Christopher Nolan hid the real clue in plain sight, and fans missed it.",
        "shift": "Look at his wedding ring. Cobb only wears it inside dream layers. In reality, the ring is gone - and in the final shot, his hand is completely bare.",
        "loop": "Which means every time you rewatch that spinning top, you already know the truth.",
    },
    "the usual suspects": {
        "hook": "Who was Keyser Soze really working for the entire time?",
        "pivot": "The director hid the biggest twist in cinema history right on the wall.",
        "shift": "Look closely at the office bulletin board. Every name, gang member, and detail Verbal mentioned was inventively lifted from the paperwork right in front of him.",
        "loop": "Which means the second you rewatch that opening police lineup, the lie is undeniable.",
    },
    "shutter island": {
        "hook": "Was Teddy Daniels really crazy at the end of Shutter Island?",
        "pivot": "Martin Scorsese gave us the answer in the very last line of dialogue.",
        "shift": "Teddy pretends to relapse because he refuses to live with what happened. He intentionally chose to die as a good man rather than live as a monster.",
        "loop": "Which means on every rewatch, that lighthouse walk hits completely differently.",
    },
    "the prestige": {
        "hook": "Did you catch how Borden pulled off his teleporting man trick?",
        "pivot": "Christopher Nolan told us the answer in the first five minutes.",
        "shift": "There was never a machine. Borden was actually identical twins living a single divided life, sacrificing everything to fool the world.",
        "loop": "Which means every time you rewatch their rivalry, the trick was always right there.",
    },
    "memento": {
        "hook": "Did Leonard Shelby ever actually solve his wife's murder in Memento?",
        "pivot": "The backward chronology hides a terrifying realization right at the start.",
        "shift": "Leonard already caught the real killer months ago. He deliberately chose to lie to himself, creating endless targets just to keep his purpose alive.",
        "loop": "Which means every time you rewatch his notes, he was chasing his own ghost.",
    },
    "fight club": {
        "hook": "Did you notice the split-second frames hidden throughout Fight Club?",
        "pivot": "David Fincher placed Tyler Durden on screen before they even officially met.",
        "shift": "In the first twenty minutes, Tyler flashes into the background for a single frame four separate times, proving the narrator's mind was fracturing from the start.",
        "loop": "Which means on your next rewatch, watch the edges of the screen.",
    },
    "interstellar": {
        "hook": "Who actually placed the wormhole near Saturn in Interstellar?",
        "pivot": "The film lets you assume it was aliens, but the truth is far deeper.",
        "shift": "It was future humanity itself. Having evolved past five dimensions, they built the bridge backward in time so Cooper could save their past.",
        "loop": "Which means on every rewatch of that tesseract, humanity saves itself.",
    },
}


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _enforce_word_limit(script: str, max_words: int = _MAX_WORDS) -> str:
    words = script.split()
    if len(words) <= max_words:
        return script
    # Truncate at sentence boundary where possible
    truncated = " ".join(words[:max_words])
    last_punct = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
    if last_punct > 0:
        return truncated[: last_punct + 1]
    return truncated + "."


# ── Mystery Script Generator ──────────────────────────────────────────────────

def build_mystery_script(title: str, overview: str = "") -> str:
    """
    Build an Open-Loop Mystery Breakdown script (50–75 words).
    """
    norm = _normalize_title(title)

    # Check curated presets
    for key, preset in _CURATED_MYSTERIES.items():
        if key in norm or norm in key:
            beats = [preset["hook"], preset["pivot"], preset["shift"], preset["loop"]]
            script = " ".join(beats)
            return _enforce_word_limit(script, _MAX_WORDS)

    # Procedural Fallback for any movie
    hook = f"Did you actually understand the real ending of {title}?"
    pivot = "The director subtly hid the definitive clue in plain sight, and most fans missed it."

    # Extract clean sentence from overview for the perspective shift
    shift = ""
    if overview:
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', overview) if s.strip()]
        if sentences:
            first_sent = sentences[0]
            if not first_sent.endswith((".", "!", "?")):
                first_sent += "."
            shift = f"Beneath the surface, {first_sent} The story is not what it seems."
    if not shift:
        shift = f"Every character interaction is carefully constructed to misdirect you from the underlying reality."

    loop = f"Which means the moment you rewatch {title}, the hidden truth clicks into place."

    beats = [hook, pivot, shift, loop]
    script = " ".join(beats)
    return _enforce_word_limit(script, _MAX_WORDS)


# ── Legacy Review Script Generator ────────────────────────────────────────────

def build_review_script(movie: dict) -> str:
    """Legacy review script generator for backward compatibility."""
    title = movie.get("title", "this movie")
    genres = ", ".join(movie.get("genres", [])[:2]) if movie.get("genres") else "Drama"
    rating = movie.get("rating")
    overview = movie.get("overview", "")

    hook = f"If you haven't seen {title} yet, stop scrolling."
    raw = [s.strip() for s in overview.split(". ") if s.strip()]
    setup = (raw[0] + ".") if raw else f"{title} is an absolute must-watch."
    genre_line = f"It's a {genres} film that pulls you in from the very first scene."

    if rating:
        why = f"It holds a {rating:.1f} out of 10 on TMDB — and that score is well earned."
    else:
        why = "The direction and performances are genuinely extraordinary."

    closer = f"Watch {title} — trust me on this one."
    return " ".join([hook, setup, genre_line, why, closer])


# ── Main Entry Point ──────────────────────────────────────────────────────────

def build_script(movie: dict, mode: str = "mystery") -> str:
    """
    Main dispatch function compatible with run_pipeline.py.
    """
    title = movie.get("title", "")
    overview = movie.get("overview", "")

    if mode == "review":
        return build_review_script(movie)
    return build_mystery_script(title=title, overview=overview)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate high-retention movie scripts (mystery or review)."
    )
    parser.add_argument("title", nargs="?", default="Inception", help="Movie title")
    parser.add_argument(
        "--mode",
        choices=["mystery", "review"],
        default="mystery",
        help="Script formula mode (default: mystery)",
    )
    args = parser.parse_args()

    movie_data = {
        "title": args.title,
        "year": "2010",
        "overview": (
            "Cobb, a skilled thief who commits corporate espionage by infiltrating "
            "the subconscious of his targets, is offered a chance to regain his old life."
        ),
        "genres": ["Action", "Science Fiction"],
        "rating": 8.4,
    }

    script = build_script(movie_data, mode=args.mode)
    words = script.split()
    word_count = len(words)
    est_duration = round(word_count / 150 * 60, 1)

    print(f"Mode       : {args.mode}")
    print(f"Title      : {args.title}")
    print(f"Script     : {script}")
    print(f"Word Count : {word_count} words")
    print(f"Est Timing : ~{est_duration}s at 150 wpm")
    if args.mode == "mystery":
        ok = _MIN_WORDS <= word_count <= _MAX_WORDS
        print(f"In Range   : {'OK (50-75 words)' if ok else 'CHECK COUNT'}")
