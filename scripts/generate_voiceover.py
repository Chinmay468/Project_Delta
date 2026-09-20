"""
Generate AI voiceover audio from a script.

Strategy (in order of preference):
  1. ElevenLabs -- if ELEVENLABS_API_KEY is set and has quota (best quality)
  2. edge-tts   -- Microsoft Edge TTS, free, no key needed, good quality

Set VOICEOVER_ENGINE=elevenlabs in config/.env to force ElevenLabs.
Default is edge-tts (free, always works).

edge-tts voice options (examples):
  en-US-GuyNeural       -- male, American
  en-US-JennyNeural     -- female, American
  en-GB-RyanNeural      -- male, British
  en-GB-SoniaNeural     -- female, British
Set EDGE_TTS_VOICE in config/.env to override.
"""

import asyncio
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "config", ".env"))

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-GuyNeural")
ENGINE = os.getenv("VOICEOVER_ENGINE", "edge-tts").lower()


def _elevenlabs(script_text: str, out_path: str) -> str:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": script_text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path


def _edge_tts(script_text: str, out_path: str) -> str:
    import edge_tts  # noqa: PLC0415

    async def _run():
        communicate = edge_tts.Communicate(script_text, EDGE_TTS_VOICE)
        await communicate.save(out_path)

    asyncio.run(_run())
    return out_path


def generate_voiceover(script_text: str, out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if ENGINE == "elevenlabs":
        if not ELEVENLABS_API_KEY:
            print("ERROR: ELEVENLABS_API_KEY not set in config/.env")
            sys.exit(1)
        print(f"    Using ElevenLabs TTS (voice {VOICE_ID})")
        return _elevenlabs(script_text, out_path)

    # Default: edge-tts (free, no key needed)
    print(f"    Using edge-tts (voice: {EDGE_TTS_VOICE}) — free, no key needed")
    try:
        return _edge_tts(script_text, out_path)
    except ImportError:
        print("ERROR: edge-tts not installed. Run: pip install edge-tts")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_voiceover.py \"script text\" [out_path]")
        sys.exit(1)
    text = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "../assets/audio/voiceover.mp3"
    generate_voiceover(text, out)
    print(f"Saved voiceover to {out}")
