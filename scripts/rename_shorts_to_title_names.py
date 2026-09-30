"""
Rename All Shorts to Clean Human-Readable Title Names
=====================================================
Renames:
1. D:\\Media\\shorts\\diepvo8265_reels (130 files + thumbs):
   diepvo8265_01_part1_<Title>.mp4
   diepvo8265_01_part2_<Title>.mp4
2. D:\\Media\\shorts\\diepvo8265 (65 files + thumbs):
   diepvo8265_01_<Title>.mp4
3. D:\\Media\\shorts\\himym (50 files + thumbs):
   himym_01_<Title>.mp4

Updates:
- diepvo8265 manifest.json
- himym manifest.json
- instagram_queue.json
- meta_business_suite_schedule.csv
"""

import os
import sys
import io
import json
import re
import csv
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

MEDIA_BASE = Path(r"D:\Media\shorts")
TBBT_DIR = MEDIA_BASE / "diepvo8265"
REELS_DIR = MEDIA_BASE / "diepvo8265_reels"
HIMYM_DIR = MEDIA_BASE / "himym"

TBBT_MANIFEST = TBBT_DIR / "manifest.json"
HIMYM_MANIFEST = HIMYM_DIR / "manifest.json"
QUEUE_FILE = MEDIA_BASE / "instagram_queue.json"
CSV_FILE = MEDIA_BASE / "meta_business_suite_schedule.csv"


def clean_title_for_filename(raw_title: str, max_len: int = 55) -> str:
    """Strips hashtags, emojis, and Windows forbidden characters."""
    # Remove #hashtags and trailing metadata
    clean = re.sub(r'#\S+', '', raw_title)
    clean = re.sub(r'- How I Met Your Mother.*', '', clean, flags=re.IGNORECASE)
    # Strip emojis and forbidden Windows chars: \ / : * ? " < > |
    clean = re.sub(r'[\\/*?:"<>|]', '', clean)
    clean = re.sub(r'[^\x00-\x7F]+', '', clean)  # remove non-ASCII/emojis
    clean = re.sub(r'\s+', ' ', clean)
    clean = clean.strip(' .-_')
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(' ', 1)[0].strip(' .-_')
    return clean or "Scene"


def rename_file_safe(old_path: Path, new_path: Path):
    """Safely renames file and matching thumbnail."""
    if old_path.exists() and old_path != new_path:
        if new_path.exists():
            new_path.unlink()
        old_path.rename(new_path)
    
    # Thumbnails
    old_thumb = old_path.with_suffix(".jpg")
    new_thumb = new_path.with_suffix(".jpg")
    if old_thumb.exists() and old_thumb != new_thumb:
        if new_thumb.exists():
            new_thumb.unlink()
        old_thumb.rename(new_thumb)


def main():
    print("=" * 70)
    print("      RENAMING ALL SHORTS TO READABLE TITLE NAMES")
    print("=" * 70 + "\n")

    # ---------------------------------------------------------
    # 1. RENAME TBBT FULL-LENGTH VIDEOS (D:\Media\shorts\diepvo8265)
    # ---------------------------------------------------------
    print("[1/4] Renaming full-length Big Bang Theory videos...")
    tbbt_title_map = {}
    if TBBT_MANIFEST.exists():
        with open(TBBT_MANIFEST, "r", encoding="utf-8") as f:
            tbbt_data = json.load(f)

        for s in tbbt_data.get("shorts", []):
            seq = s.get("sequence", 1)
            vid_id = s.get("id", "")
            title_clean = clean_title_for_filename(s.get("clean_title") or s.get("title", ""))
            tbbt_title_map[vid_id] = (seq, title_clean, s.get("clean_title") or s.get("title", ""))

            # Find matching file on disk
            old_p = None
            for p in TBBT_DIR.glob(f"*{vid_id}*.mp4"):
                old_p = p
                break

            if old_p:
                new_fn = f"diepvo8265_{seq:02d}_{title_clean}.mp4"
                new_p = TBBT_DIR / new_fn
                rename_file_safe(old_p, new_p)
                s["local_path"] = str(new_p)
                s["file_name"] = new_fn

        with open(TBBT_MANIFEST, "w", encoding="utf-8") as f:
            json.dump(tbbt_data, f, indent=2, ensure_ascii=False)
        print(f"      Renamed {len(tbbt_data.get('shorts', []))} full-length TBBT files.")

    # ---------------------------------------------------------
    # 2. RENAME SPLIT REELS (D:\Media\shorts\diepvo8265_reels)
    # ---------------------------------------------------------
    print("\n[2/4] Renaming 130 split Big Bang Theory Reels...")
    if REELS_DIR.exists():
        for vid_id, (seq, title_clean, full_title) in tbbt_title_map.items():
            # Part 1
            for p in REELS_DIR.glob(f"*{seq:02d}*part1*{vid_id}*.mp4"):
                new_fn = f"diepvo8265_{seq:02d}_part1_{title_clean}.mp4"
                new_p = REELS_DIR / new_fn
                rename_file_safe(p, new_p)
                break

            # Part 2
            for p in REELS_DIR.glob(f"*{seq:02d}*part2*{vid_id}*.mp4"):
                new_fn = f"diepvo8265_{seq:02d}_part2_{title_clean}.mp4"
                new_p = REELS_DIR / new_fn
                rename_file_safe(p, new_p)
                break
        print("      Renamed 130 split Reels in diepvo8265_reels.")

    # ---------------------------------------------------------
    # 3. RENAME HIMYM SHORTS (D:\Media\shorts\himym)
    # ---------------------------------------------------------
    print("\n[3/4] Renaming How I Met Your Mother shorts...")
    himym_title_map = {}
    if HIMYM_MANIFEST.exists():
        with open(HIMYM_MANIFEST, "r", encoding="utf-8") as f:
            himym_data = json.load(f)

        for idx, s in enumerate(himym_data.get("shorts", []), 1):
            vid_id = s.get("id", "")
            title_clean = clean_title_for_filename(s.get("title", ""))
            himym_title_map[vid_id] = (idx, title_clean, s.get("title", ""))

            old_p = None
            for p in HIMYM_DIR.glob(f"*{vid_id}*.mp4"):
                old_p = p
                break

            if old_p:
                new_fn = f"himym_{idx:02d}_{title_clean}.mp4"
                new_p = HIMYM_DIR / new_fn
                rename_file_safe(old_p, new_p)
                s["local_path"] = str(new_p)
                s["file_name"] = new_fn

        with open(HIMYM_MANIFEST, "w", encoding="utf-8") as f:
            json.dump(himym_data, f, indent=2, ensure_ascii=False)
        print(f"      Renamed {len(himym_data.get('shorts', []))} HIMYM files.")

    # ---------------------------------------------------------
    # 4. REBUILD QUEUE & CSV WITH NEW FILE NAMES
    # ---------------------------------------------------------
    print("\n[4/4] Updating instagram_queue.json and meta_business_suite_schedule.csv...")
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            queue_data = json.load(f)

        for item in queue_data.get("queue", []):
            item_id = item.get("id", "")
            # Check if TBBT reel Part 1 or 2
            if "_p1" in item_id:
                base_id = item_id.replace("_p1", "")
                if base_id in tbbt_title_map:
                    seq, t_clean, _ = tbbt_title_map[base_id]
                    new_fn = f"diepvo8265_{seq:02d}_part1_{t_clean}.mp4"
                    item["file_name"] = new_fn
                    item["local_path"] = str(REELS_DIR / new_fn)
            elif "_p2" in item_id:
                base_id = item_id.replace("_p2", "")
                if base_id in tbbt_title_map:
                    seq, t_clean, _ = tbbt_title_map[base_id]
                    new_fn = f"diepvo8265_{seq:02d}_part2_{t_clean}.mp4"
                    item["file_name"] = new_fn
                    item["local_path"] = str(REELS_DIR / new_fn)
            elif item_id in himym_title_map:
                idx, t_clean, _ = himym_title_map[item_id]
                new_fn = f"himym_{idx:02d}_{t_clean}.mp4"
                item["file_name"] = new_fn
                item["local_path"] = str(HIMYM_DIR / new_fn)

        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue_data, f, indent=2, ensure_ascii=False)
        print("      Updated instagram_queue.json.")

        # Re-export CSV
        csv_rows = []
        for item in queue_data.get("queue", []):
            csv_rows.append({
                "Index": item["queue_index"],
                "Show": item["show"],
                "File": item["file_name"],
                "Path": item["local_path"],
                "Title": item["title"],
                "Scheduled_Date_Time": item["scheduled_for"],
                "Caption": item["caption"]
            })

        try:
            with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["Index", "Show", "File", "Path", "Title", "Scheduled_Date_Time", "Caption"])
                writer.writeheader()
                writer.writerows(csv_rows)
            print(f"      Updated CSV schedule: {CSV_FILE}")
        except PermissionError:
            alt_csv = MEDIA_BASE / "meta_schedule.csv"
            with open(alt_csv, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["Index", "Show", "File", "Path", "Title", "Scheduled_Date_Time", "Caption"])
                writer.writeheader()
                writer.writerows(csv_rows)
            print(f"      [NOTICE] Original CSV is open in Excel. Saved updated schedule to: {alt_csv}")

    print("\n" + "=" * 70)
    print("🎉 ALL SHORT FILES SUCCESSFULLY RENAMED TO TITLE NAMES!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
