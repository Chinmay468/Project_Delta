"""
Project Delta — YouTube Channel Shorts Bulk Downloader
Downloads all shorts from any specified YouTube channel into D:\\Media\\shorts\\<channel_name>\\
with metadata tracking, resume capability, and auto-muxing.
"""

import os
import sys
import re
import time
import json
import random
import subprocess
from typing import List, Dict, Any, Optional

# Ensure UTF-8 output on Windows console
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_SHORTS_ROOT = r"D:\Media\shorts"

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from download_short import download_youtube_short, normalize_youtube_url


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """Sanitize title for safe Windows filenames."""
    clean = re.sub(r'[\\/*?:"<>|#\n\r\t]', "", name).strip()
    clean = re.sub(r"\s+", " ", clean)
    return clean[:max_length].strip()


def extract_channel_shorts_list(channel_url: str) -> List[Dict[str, Any]]:
    """Fetch the list of all shorts entries from a channel URL."""
    import yt_dlp

    # Standardize channel URL to /shorts tab
    url = channel_url.rstrip("/")
    if not url.endswith("/shorts"):
        shorts_url = f"{url}/shorts"
    else:
        shorts_url = url

    print(f"Extracting shorts playlist from: {shorts_url}...")

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
        "socket_timeout": 30,
        "retries": 5,
    }

    entries = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        res = ydl.extract_info(shorts_url, download=False)
        raw_entries = res.get("entries", [])
        channel_name = res.get("channel") or res.get("uploader") or "unknown_channel"

        for item in raw_entries:
            if not item:
                continue
            vid_id = item.get("id")
            title = item.get("title", "Untitled")
            views = item.get("view_count") or 0
            dur = item.get("duration") or 0
            entries.append({
                "id": vid_id,
                "title": title,
                "view_count": views,
                "duration": dur,
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "channel": channel_name,
            })

    return entries


def download_all_channel_shorts(
    channel_url: str,
    output_base_dir: str = DEFAULT_SHORTS_ROOT,
    folder_name: Optional[str] = None,
    limit: Optional[int] = None,
    filter_keywords: Optional[List[str]] = None,
    delay_range: tuple = (1.5, 3.0),
) -> Dict[str, Any]:
    """Download every short from a YouTube channel into its own subfolder."""
    # Extract channel handle or name if not provided
    if not folder_name:
        m = re.search(r"@([\w.-]+)", channel_url)
        folder_name = m.group(1) if m else "channel_shorts"

    target_dir = os.path.join(output_base_dir, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    manifest_file = os.path.join(target_dir, "manifest.json")
    upload_queue_file = os.path.join(target_dir, "upload_queue.json")

    print("=" * 80)
    print(f"  DOWNLOADING ALL SHORTS FROM CHANNEL: {channel_url}")
    print(f"  Destination Folder: {target_dir}")
    print("=" * 80 + "\n")

    shorts = extract_channel_shorts_list(channel_url)
    
    # Filter keywords if provided
    if filter_keywords:
        filtered = []
        for s in shorts:
            t = s["title"].lower()
            if any(k.lower() in t for k in filter_keywords):
                filtered.append(s)
        shorts = filtered
        print(f"Filtered down to {len(shorts)} shorts matching keywords: {filter_keywords}")

    if limit and limit > 0:
        shorts = shorts[:limit]
        print(f"Limited download to first {len(shorts)} shorts.")

    total_count = len(shorts)
    print(f"Total shorts to process: {total_count}\n")

    manifest = {
        "channel_url": channel_url,
        "channel_folder": target_dir,
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_shorts_count": total_count,
        "shorts": [],
    }

    downloaded_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, item in enumerate(shorts, 1):
        vid_id = item["id"]
        raw_title = item["title"]
        clean_title = sanitize_filename(raw_title)
        prefix = f"{folder_name}_{idx:02d}_{clean_title}_{vid_id}"

        # Check if already downloaded
        existing_file = None
        for fname in os.listdir(target_dir):
            if fname.endswith(".mp4") and vid_id in fname:
                full_p = os.path.join(target_dir, fname)
                if os.path.getsize(full_p) > 100_000:
                    existing_file = full_p
                    break

        if existing_file:
            size_mb = os.path.getsize(existing_file) / (1024 * 1024)
            print(f"[{idx:02d}/{total_count}] Already cached: {os.path.basename(existing_file)} ({size_mb:.1f} MB)")
            item["local_path"] = existing_file
            item["file_size_mb"] = round(size_mb, 2)
            item["status"] = "cached"
            manifest["shorts"].append(item)
            skipped_count += 1
            continue

        print(f"[{idx:02d}/{total_count}] Downloading: \"{raw_title[:60]}\" ({vid_id})...")
        download_success = False
        last_err = ""

        for attempt in range(1, 4):
            try:
                res = download_youtube_short(
                    url_or_id=item["url"],
                    output_dir=target_dir,
                    filename=f"{folder_name}_{idx:02d}_{vid_id}",
                    quiet=True,
                )
                final_path = res["video_path"]
                size_mb = os.path.getsize(final_path) / (1024 * 1024)

                # Probe duration
                cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', final_path]
                probe = subprocess.run(cmd, capture_output=True, text=True)
                try:
                    actual_dur = float(json.loads(probe.stdout)['format']['duration'])
                except Exception:
                    actual_dur = item.get("duration", 0)

                print(f"    Saved: {os.path.basename(final_path)} ({actual_dur:.1f}s, {size_mb:.1f} MB, {res.get('width')}x{res.get('height')})")
                item["local_path"] = final_path
                item["actual_duration"] = round(actual_dur, 1)
                item["file_size_mb"] = round(size_mb, 2)
                item["status"] = "downloaded"
                manifest["shorts"].append(item)
                downloaded_count += 1
                download_success = True
                break

            except Exception as e:
                last_err = str(e)
                if attempt < 3:
                    print(f"    [Retry {attempt}/3] Network pause, retrying in 3s... ({e})")
                    time.sleep(3.0)

        if not download_success:
            print(f"    [Error] Failed to download {vid_id} after 3 attempts: {last_err}")
            item["status"] = f"error: {last_err}"
            manifest["shorts"].append(item)
            failed_count += 1

        # Incremental manifest write
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Automatically generate upload_queue.json for scheduling
    valid_shorts = [s for s in manifest["shorts"] if s.get("status") in ["downloaded", "cached"] and os.path.exists(s.get("local_path", ""))]
    if valid_shorts:
        from datetime import datetime, date, timedelta
        # Start after the latest scheduled date if known, otherwise 2026-11-07
        start_date = date(2026, 11, 7)
        upload_queue = {
            "channel_source": channel_url,
            "total_items": len(valid_shorts),
            "publish_hour_utc": 12, # 12:30 UTC = 18:00 IST
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "queue": []
        }

        for q_idx, item in enumerate(valid_shorts, 1):
            curr_date = start_date + timedelta(days=q_idx - 1)
            raw_t = item.get("title", "")
            # Clean title
            core_t = re.sub(r'#\S+', '', raw_t).strip().strip(" -.")
            if len(core_t) > 65:
                core_t = core_t[:62] + "..."
            clean_t = f"{core_t} 🤣 #Shorts #HIMYM #HowIMetYourMother"
            if len(clean_t) > 100:
                clean_t = clean_t[:97] + "..."

            desc = (
                f"{core_t} 🤣\n\n"
                f"Classic comedy moment from How I Met Your Mother!\n\n"
                f"🔔 Subscribe to Sitcom Vault Daily (@SitcomVaultDaily) for daily comedy sitcom shorts!\n"
                f"👍 Like and share if you love Barney Stinson!\n\n"
                f"#Shorts #HIMYM #HowIMetYourMother #BarneyStinson #TedMosby #MarshallEriksen #RobinScherbatsky #LilyAldrin #Sitcom #Comedy #Funny #Legendary"
            )

            tags = [
                "shorts", "himym", "how i met your mother", "barney stinson",
                "ted mosby", "marshall eriksen", "robin scherbatsky", "lily aldrin",
                "sitcom", "comedy", "funny shorts", "legendary", "bazinga"
            ]

            upload_queue["queue"].append({
                "queue_index": q_idx,
                "id": item["id"],
                "local_path": item["local_path"],
                "file_name": os.path.basename(item["local_path"]),
                "title": clean_t,
                "description": desc,
                "tags": tags,
                "categoryId": "23",
                "scheduled_date": curr_date.strftime("%Y-%m-%d"),
                "publish_at_utc": f"{curr_date.strftime('%Y-%m-%d')}T12:30:00.000Z",
                "status": "pending",
                "youtube_id": None,
                "youtube_url": None,
                "uploaded_at": None
            })

        with open(upload_queue_file, "w", encoding="utf-8") as f:
            json.dump(upload_queue, f, indent=2, ensure_ascii=False)
        print(f"  Upload Queue: {upload_queue_file} ({len(upload_queue['queue'])} items queued)")

    print("\n" + "=" * 80)
    print(f"  DOWNLOAD SUMMARY FOR {channel_url}")
    print(f"  Total Shorts: {total_count}")
    print(f"  Newly Downloaded: {downloaded_count}")
    print(f"  Already Cached: {skipped_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Manifest: {manifest_file}")
    print("=" * 80)

    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download all shorts from a YouTube channel")
    parser.add_argument("channel_url", nargs="?", default="https://www.youtube.com/@diepvo8265", help="YouTube Channel URL")
    parser.add_argument("--output", default=DEFAULT_SHORTS_ROOT, help="Base output directory")
    parser.add_argument("--folder", default=None, help="Target folder name inside output directory")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of shorts to download")
    parser.add_argument("--filter", nargs="*", default=None, help="Keywords to filter shorts titles")
    args = parser.parse_args()

    download_all_channel_shorts(
        args.channel_url,
        output_base_dir=args.output,
        folder_name=args.folder,
        limit=args.limit,
        filter_keywords=args.filter
    )
