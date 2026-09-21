# Project Delta — Local AI Clip Cutter & YouTube Shorts Engine

An end-to-end, fully self-hosted local AI engine that automatically transcribes full-length video footage, detects high-retention 30–60s moments, applies intelligent face-tracking vertical re-framing (9:16), burns in active yellow karaoke subtitles, and renders ready-to-upload YouTube Shorts.

Also includes the **High-Retention Movie Mystery Engine** for generating 4-part open-loop breakdown Shorts with dynamic multi-scene cuts and cinematic color grading.

---

## Features

- 🎙️ **Local Word-Level Audio Transcription**: Powered by `faster-whisper` (`base` model, `int8` CPU quantization or CUDA) with caching in `assets/cache/`.
- 🧠 **Intelligent Viral Moment Detection**: NLP/heuristic scoring that detects question-and-answer patterns, punch words, speech cadence (120–170 wpm), and snaps to silence pauses (>0.4s) to eliminate awkward sentence cutoffs.
- 👤 **Face-Tracking Auto-Cropper**: Dynamic 9:16 vertical re-framing using a 3-tier fallback (MediaPipe $\rightarrow$ OpenCV DNN YuNet $\rightarrow$ Haar Cascade) with Exponential Moving Average ($\alpha = 0.2$) smoothing.
- ✨ **Kinetic Karaoke Subtitles**: Active word highlighted in bright yellow (`&H00FFFF&`) and inactive words in white (`&H00FFFFFF&`) with safe-zone margin (`MarginV=240`) above Shorts UI overlays.
- 🎨 **Cinematic Color Grading**: Unified grading filter (`eq=contrast=1.12:saturation=1.15:brightness=-0.02`).
- 🚀 **Automated YouTube Shorts Publishing**: Direct OAuth2 integration with YouTube Data API v3 for immediate publishing or scheduled release.

---

## Setup & Requirements

### 1. External Tools
- **FFmpeg & FFprobe**: Must be installed and available on system `PATH` (or Windows WinGet links directory).
  - Windows: `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

### 2. Python Environment
Install required dependencies:
```bash
pip install -r requirements.txt
```
*(Note: If installing in an externally managed environment, add `--break-system-packages`.)*

### 3. API Keys (Optional)
Copy `config/.env.example` to `config/.env`:
- `TMDB_API_KEY`: For movie metadata fetching.
- `ELEVENLABS_API_KEY`: For ElevenLabs narration (or fallback to free `edge-tts`).
- `config/client_secret.json`: Google Cloud OAuth2 credentials for YouTube uploading.

---

## Quick Start & Usage

### 🚀 Interactive Studio CLI (Recommended)
Run the entire suite through the interactive menu-driven interface without needing to memorize flags:
```powershell
python main.py
```
From the interactive menu, you can:
- Auto-extract top viral moments from any video
- Extract custom scene timestamps with face-tracking
- Run movie mystery breakdown generation
- Test and access modular utilities (transcription, scoring, face-cropping, karaoke burn)
- Browse and open rendered Shorts in Windows player / explorer
- Run a system health check on FFmpeg, YuNet ONNX, and API keys

---

### CLI Direct Commands

#### 1. Local AI Clip Cutter (Auto-Detect Top Viral Clips)
Automatically transcribes, scores, face-crops, and captions the top viral moments from a full-length movie:
```powershell
python scripts/run_ai_cutter.py "D:\Media\movies\The Usual Suspects.mkv" --top 3
```

### 2. Extract a Specific Scene Timestamp
Manually crop and caption a specific scene with face tracking and kinetic subtitles:
```powershell
python scripts/run_ai_cutter.py "path/to/movie.mkv" -s 01:41:30 -t 40
```

### 3. High-Retention Mystery Narrative Shorts
Generate a 4-part open-loop mystery Short from downloaded clips or posters:
```powershell
python scripts/run_pipeline.py "The Usual Suspects" --mode mystery --force
```

### 4. Upload / Schedule directly to YouTube
```powershell
python scripts/run_ai_cutter.py "path/to/movie.mkv" --top 1 --upload
```

---

## Repository Structure

```
├── config/
│   ├── .env.example              # Sample environment configuration
│   └── script_template.txt       # 4-part retention script structure
├── scripts/
│   ├── run_ai_cutter.py          # End-to-end AI Clip Cutter CLI orchestrator
│   ├── transcribe.py             # Local audio extraction & faster-whisper transcription
│   ├── detect_clips.py           # NLP viral moment detection & silence gap snapping
│   ├── face_crop.py              # Face detection (MediaPipe/OpenCV DNN) & 9:16 auto-crop
│   ├── build_video.py            # FFmpeg kinetic karaoke ASS & multi-clip builder
│   ├── cut_clip.py               # Standalone lossless & vertical scene cutter
│   ├── run_pipeline.py           # Mystery shorts pipeline orchestrator
│   ├── generate_script.py        # 4-part open-loop script generator
│   ├── generate_voiceover.py     # edge-tts / ElevenLabs narration generator
│   ├── fetch_movie_data.py       # TMDB API metadata fetcher
│   └── upload_video.py           # YouTube Data API v3 publisher
├── assets/
│   ├── models/                   # Local face detection weights (YuNet ONNX, Haar XML)
│   ├── audio/                    # Extracted and generated audio files
│   ├── cache/                    # Cached Whisper transcripts
│   ├── clips/                    # Cut video clips
│   ├── output/                   # Final rendered 1080x1920 YouTube Shorts
│   └── posters/                  # Movie posters
├── requirements.txt              # Python dependencies
├── .gitignore                    # Secrets, video binaries, and cache exclusion
└── README.md
```

---

## Legal & Compliance

- **No Stream Scraping**: This tool processes only locally provided video files and does not scrape or rip copyrighted streams.
- **Transformative Creation**: Combines critical analysis, commentary, kinetic typography, and editorial framing under Fair Use principles.
