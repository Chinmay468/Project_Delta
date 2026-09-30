"""
Project Delta — YouTube Shorts Downloader
High-quality downloader for YouTube Shorts & Videos powered by yt-dlp.

Features:
  - Supports standard URLs, /shorts/ URLs, youtu.be shortlinks, or raw video IDs.
  - Downloads highest available quality (up to 1080p/4K) with audio muxed to MP4.
  - Automatically incorporates Node.js runtime and EJS challenge solvers for robust extraction.
  - Integrates directly into Project Delta: saved clips are instantly available in assets/clips/.
  - Programmatic API and interactive CLI modes.
"""

import os
import sys
import re
import io
import shutil
import subprocess
from typing import Optional, Dict, Any

# Ensure stdout handles UTF-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")
CLIPS_DIR = os.path.join(ASSETS_DIR, "clips")
CACHE_DIR = os.path.join(ASSETS_DIR, "cache")

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

try:
    from build_video import _find_tool
except ImportError:
    def _find_tool(name: str) -> str:
        return shutil.which(name) or name

try:
    from transcribe import slugify
except ImportError:
    def slugify(text: str) -> str:
        text = re.sub(r"[^\w\s-]", "", text).strip().lower()
        return re.sub(r"[-\s]+", "_", text)


def normalize_youtube_url(url_or_id: str) -> str:
    """Normalize user input to a canonical YouTube URL."""
    s = url_or_id.strip()
    if not s:
        return ""
    # Raw 11-char video ID (alphanumeric, -, _)
    if re.fullmatch(r"[\w-]{11}", s):
        return f"https://www.youtube.com/watch?v={s}"
    # Shorts URL: youtube.com/shorts/<id> -> canonical
    m = re.search(r"youtube\.com/shorts/([\w-]{11})", s)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    # Shortlink: youtu.be/<id> -> canonical
    m = re.search(r"youtu\.be/([\w-]{11})", s)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    # Already a standard URL or search query
    return s


def fetch_short_metadata(url_or_id: str) -> Optional[Dict[str, Any]]:
    """Extract metadata for a YouTube Short without downloading."""
    import yt_dlp

    url = normalize_youtube_url(url_or_id)
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if "entries" in info:
                info = info["entries"][0]
            
            w = info.get("width") or 0
            h = info.get("height") or 0
            return {
                "id": info.get("id"),
                "title": info.get("title", "Untitled"),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown Channel"),
                "channel_url": info.get("channel_url"),
                "view_count": info.get("view_count", 0),
                "like_count": info.get("like_count", 0),
                "description": info.get("description", ""),
                "tags": info.get("tags", []),
                "thumbnail": info.get("thumbnail"),
                "webpage_url": info.get("webpage_url", url),
                "width": w,
                "height": h,
                "is_vertical": bool(h > w) if (w and h) else True,
            }
    except Exception as e:
        print(f"Error fetching metadata: {e}")
        return None


def download_youtube_short(
    url_or_id: str,
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
    max_height: int = 1080,
    quiet: bool = False,
) -> Dict[str, Any]:
    """
    Download a YouTube Short or video in top quality, muxed into MP4.
    
    Args:
        url_or_id: YouTube URL (shorts, watch, or ID)
        output_dir: Directory to save the video (defaults to assets/clips)
        filename: Optional custom filename (defaults to sanitized title + id)
        max_height: Maximum vertical resolution (e.g. 1080)
        quiet: Suppress progress outputs
        
    Returns:
        dict containing video_path, metadata, and status.
    """
    import yt_dlp

    url = normalize_youtube_url(url_or_id)
    target_dir = os.path.abspath(output_dir or CLIPS_DIR)
    os.makedirs(target_dir, exist_ok=True)

    ffmpeg_bin = _find_tool("ffmpeg")
    ffmpeg_dir = os.path.dirname(ffmpeg_bin) if os.path.isabs(ffmpeg_bin) else None

    # Custom output template
    if filename:
        clean_name = os.path.splitext(filename)[0]
        outtmpl = os.path.join(target_dir, f"{clean_name}.%(ext)s")
    else:
        outtmpl = os.path.join(target_dir, "%(title).60s_%(id)s.%(ext)s")

    ydl_opts: Dict[str, Any] = {
        "format": f"bestvideo[ext=mp4][height<={max_height}]+bestaudio[ext=m4a]/bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best",
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
        "quiet": quiet,
        "no_warnings": False,
        "windowsfilenames": True,
        "restrictfilenames": False,
        "socket_timeout": 30,
        "retries": 10,
        "fragment_retries": 10,
    }

    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if "entries" in info:
            info = info["entries"][0]

        # Determine the final downloaded filepath
        downloaded_file = ydl.prepare_filename(info)
        # yt-dlp might have changed the extension to mp4 after muxing
        base, _ = os.path.splitext(downloaded_file)
        final_mp4 = f"{base}.mp4"
        if not os.path.exists(final_mp4) and os.path.exists(downloaded_file):
            final_mp4 = downloaded_file

    w = info.get("width") or 0
    h = info.get("height") or 0

    return {
        "status": "success",
        "video_path": os.path.abspath(final_mp4),
        "id": info.get("id"),
        "title": info.get("title"),
        "duration": info.get("duration", 0),
        "uploader": info.get("uploader", "Unknown"),
        "width": w,
        "height": h,
        "is_vertical": bool(h > w) if (w and h) else True,
        "webpage_url": info.get("webpage_url", url),
        "description": info.get("description", ""),
        "tags": info.get("tags", []),
        "thumbnail": info.get("thumbnail"),
    }


def interactive_downloader():
    """Interactive CLI terminal flow for downloading YouTube Shorts."""
    print("=" * 70)
    print("  PROJECT DELTA — YOUTUBE SHORTS DOWNLOADER")
    print("  High-Resolution MP4 Extraction • Audio Sync • Direct Studio Intake")
    print("=" * 70 + "\n")

    raw_input = input("Enter YouTube Short URL or Video ID > ").strip()
    if not raw_input:
        print("No URL provided. Exiting.")
        return

    print("\nFetching video information...")
    meta = fetch_short_metadata(raw_input)
    if not meta:
        print("Failed to retrieve video metadata. Please check the URL and internet connection.")
        return

    print("\n" + "-" * 50)
    print(f"Title:       {meta['title']}")
    print(f"Channel:     {meta['uploader']}")
    print(f"Duration:    {meta['duration']}s")
    if meta['width'] and meta['height']:
        orientation = "Vertical 9:16 (Shorts)" if meta['is_vertical'] else "Horizontal 16:9"
        print(f"Resolution:  {meta['width']}x{meta['height']} ({orientation})")
    print(f"Views:       {meta['view_count']:,}")
    print("-" * 50 + "\n")

    confirm = input("Download this short to assets/clips? [Y/n] > ").strip().lower()
    if confirm in ("n", "no"):
        print("Download canceled.")
        return

    print("\nDownloading and merging highest-quality stream...")
    try:
        res = download_youtube_short(raw_input)
        video_path = res["video_path"]
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"\n[OK] Successfully downloaded!")
        print(f"Path: {video_path} ({file_size_mb:.1f} MB)")

        print("\nNext actions available in Project Delta:")
        print("  [1] Transcribe Audio (faster-whisper word timestamps)")
        print("  [2] Detect & Score Viral Moments")
        print("  [3] Vertical Reframe / Face Crop")
        print("  [4] Open Video in Windows Player")
        print("  [0] Done / Exit")

        act = input("\nSelect action [default: 0] > ").strip()
        if act == "1":
            from transcribe import transcribe_video
            print("\nTranscribing audio...")
            t_res = transcribe_video(video_path)
            print(f"Transcript generated: {t_res.get('text', '')[:100]}...")
        elif act == "2":
            from detect_clips import find_top_n_clips
            print("\nDetecting viral moments...")
            clips = find_top_n_clips(video_path, n=3)
            for c in clips:
                print(f"  Rank {c['rank']}: {c['start']}s -> {c['end']}s | Hook: {c.get('hook_title')}")
        elif act == "3":
            from face_crop import crop_to_vertical
            out_crop = os.path.splitext(video_path)[0] + "_vertical.mp4"
            print("\nReframing to 9:16...")
            crop_to_vertical(video_path, 0, res["duration"] or 30, out_crop)
            print(f"Reframed clip saved: {out_crop}")
        elif act == "4":
            if sys.platform == "win32":
                os.startfile(video_path)
            else:
                subprocess.run(["xdg-open", video_path])

    except Exception as e:
        print(f"\n[ERROR] Download failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg_url = sys.argv[1]
        out_arg = sys.argv[2] if len(sys.argv) > 2 else None
        res = download_youtube_short(arg_url, output_dir=out_arg)
        print(f"Downloaded to: {res['video_path']}")
    else:
        interactive_downloader()
