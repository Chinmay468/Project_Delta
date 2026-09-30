"""
Diepvo8265 YouTube Shorts Full Sync & Sequential Downloader
===========================================================
1. Fetches all 65 Shorts from https://www.youtube.com/@diepvo8265/shorts in exact YouTube sequence.
2. Re-indexes and renames existing cached files to match their true 1-65 YouTube sequence.
3. Downloads all missing Shorts with best quality MP4.
4. Generates high-quality frame thumbnails (.jpg) for each video.
5. Updates manifest.json, instagram_queue.json, and meta_business_suite_schedule.csv.
"""

import os
import sys
import io
import json
import time
import re
import csv
from pathlib import Path

# Force UTF-8 stdout
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import yt_dlp
import cv2

TARGET_DIR = Path(r"D:\Media\shorts\diepvo8265")
MANIFEST_PATH = TARGET_DIR / "manifest.json"
QUEUE_PATH = Path(r"D:\Media\shorts\instagram_queue.json")
CSV_PATH = Path(r"D:\Media\shorts\meta_business_suite_schedule.csv")
CHANNEL_URL = "https://www.youtube.com/@diepvo8265/shorts"


def sanitize_title(title: str) -> str:
    clean = re.sub(r'#\S+', '', title).strip()
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip(". -")


def extract_thumbnail(video_path: Path) -> Path:
    thumb_path = video_path.with_suffix(".jpg")
    if thumb_path.exists() and thumb_path.stat().st_size > 1000:
        return thumb_path
    try:
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_MSEC, 1500)
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_MSEC, 0)
            ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            cv2.imwrite(str(thumb_path), frame)
            return thumb_path
    except Exception as e:
        print(f"    [WARN] Thumbnail extraction: {e}")
    return None


def sync_and_download():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("      SYNCING @diepvo8265 SHORTS IN EXACT YOUTUBE SEQUENCE")
    print("=" * 70)
    print(f"Channel: {CHANNEL_URL}")
    print(f"Target:  {TARGET_DIR}\n")

    # Step 1: Fetch exact channel sequence from YouTube
    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True
    }

    print("[1/5] Extracting video list from YouTube...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        res = ydl.extract_info(CHANNEL_URL, download=False)
        yt_entries = res.get("entries", [])

    total_yt = len(yt_entries)
    print(f"      Found {total_yt} shorts on @diepvo8265.\n")

    # Map existing files on disk by video ID
    existing_files_by_id = {}
    for p in TARGET_DIR.glob("*.mp4"):
        if p.stat().st_size > 100_000:
            for e in yt_entries:
                vid_id = e.get("id")
                if vid_id and vid_id in p.name:
                    existing_files_by_id[vid_id] = p
                    break

    print(f"[2/5] Matched {len(existing_files_by_id)} already downloaded files on disk.")

    manifest_entries = []
    downloaded_new = 0
    reused = 0

    # Step 2: Download / re-sequence each video 1 to N
    print("\n[3/5] Processing all 65 videos in exact YouTube order:")
    for idx, e in enumerate(yt_entries, 1):
        vid_id = e["id"]
        title = e.get("title", "")
        clean_t = sanitize_title(title)
        expected_filename = f"diepvo8265_{idx:02d}_{vid_id}.mp4"
        expected_path = TARGET_DIR / expected_filename

        if vid_id in existing_files_by_id:
            src_path = existing_files_by_id[vid_id]
            if src_path != expected_path:
                print(f"  [{idx:02d}/{total_yt}] Renaming #{idx:02d}: {src_path.name} -> {expected_filename}")
                if expected_path.exists() and expected_path != src_path:
                    expected_path.unlink()
                src_path.rename(expected_path)
                # Also rename thumb if exists
                old_thumb = src_path.with_suffix(".jpg")
                if old_thumb.exists():
                    new_thumb = expected_path.with_suffix(".jpg")
                    if new_thumb.exists():
                        new_thumb.unlink()
                    old_thumb.rename(new_thumb)
            else:
                print(f"  [{idx:02d}/{total_yt}] Cached #{idx:02d}: {expected_filename} ({expected_path.stat().st_size / (1024*1024):.1f} MB)")
            reused += 1
        else:
            # Need to download
            print(f"  [{idx:02d}/{total_yt}] Downloading #{idx:02d}: {title[:50]} ({vid_id})...")
            dl_opts = {
                "outtmpl": str(expected_path),
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "quiet": True,
                "no_warnings": True,
                "overwrites": True
            }
            try:
                with yt_dlp.YoutubeDL(dl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/shorts/{vid_id}"])
                downloaded_new += 1
                size_mb = expected_path.stat().st_size / (1024 * 1024)
                print(f"         Saved #{idx:02d}: {expected_filename} ({size_mb:.1f} MB)")
                time.sleep(1)  # safe delay
            except Exception as dl_err:
                print(f"         ERROR downloading {vid_id}: {dl_err}")
                continue

        # Extract thumbnail
        extract_thumbnail(expected_path)

        manifest_entries.append({
            "id": vid_id,
            "sequence": idx,
            "title": title,
            "clean_title": clean_t,
            "local_path": str(expected_path),
            "file_name": expected_filename,
            "file_size_mb": round(expected_path.stat().st_size / (1024 * 1024), 2) if expected_path.exists() else 0,
            "url": f"https://www.youtube.com/shorts/{vid_id}"
        })

    # Step 3: Write manifest.json
    manifest_data = {
        "channel_name": "@diepvo8265",
        "channel_url": CHANNEL_URL,
        "total_shorts": len(manifest_entries),
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "shorts": manifest_entries
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    print(f"\n[4/5] Saved updated manifest: {MANIFEST_PATH} ({len(manifest_entries)} shorts)")

    # Step 4: Re-build instagram_queue.json and CSV
    print("[5/5] Re-building Instagram Queue and Meta Business Suite schedule...")
    from instagram_reels_uploader import build_or_sync_queue
    build_or_sync_queue()

    # Re-export CSV
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        q_data = json.load(f)

    from datetime import datetime, timedelta
    start = datetime.now() + timedelta(days=1)
    start = start.replace(hour=19, minute=30, second=0, microsecond=0)
    rows = []
    for idx, x in enumerate(q_data.get("queue", []), 1):
        sched = start + timedelta(days=idx-1)
        rows.append({
            "Index": idx,
            "Show": x.get("show"),
            "File": x.get("file_name"),
            "Path": x.get("local_path"),
            "Title": x.get("title"),
            "Scheduled_Date_Time": sched.strftime("%Y-%m-%d %H:%M"),
            "Caption": x.get("caption")
        })

    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["Index", "Show", "File", "Path", "Title", "Scheduled_Date_Time", "Caption"])
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "=" * 70)
    print(f"🎉 SYNC COMPLETE!")
    print(f"   Total Sequenced:   {len(manifest_entries)} / {total_yt}")
    print(f"   Reused & Renamed:  {reused}")
    print(f"   Newly Downloaded:  {downloaded_new}")
    print(f"   Instagram Queue:   {QUEUE_PATH}")
    print(f"   Meta CSV Schedule: {CSV_PATH}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    sync_and_download()
