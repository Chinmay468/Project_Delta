"""
Download and Process New Shorts from @diepvo8265
================================================
1. Downloads the 9 new shorts from https://www.youtube.com/@diepvo8265/shorts to D:\\Media\\shorts\\diepvo8265.
2. Generates video thumbnails (.jpg).
3. Splits each short into Part 1 and Part 2 in D:\\Media\\shorts\\diepvo8265_reels (under 90s limit).
4. Generates thumbnails for all split parts.
5. Updates D:\\Media\\shorts\\diepvo8265\\manifest.json.
6. Appends the 18 new Reels to data/instagram_queue.json.
"""

import os
import sys
import io
import json
import re
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import yt_dlp
import cv2

RAW_DIR = Path(r"D:\Media\shorts\diepvo8265")
REELS_DIR = Path(r"D:\Media\shorts\diepvo8265_reels")
MANIFEST_PATH = RAW_DIR / "manifest.json"
REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = REPO_ROOT / "data" / "instagram_queue.json"


NEW_SHORTS = [
    {
        "index": 66,
        "id": "pX23g56utzQ",
        "title": "Sheldon goes to watch Penny’s play.🤣 #sitcom #bbbgshow #funny #movie #tvshow",
    },
    {
        "index": 67,
        "id": "i1KKxBAGVfI",
        "title": "Sheldon tries really hard for Leonard and Penny’s relationship.😂 #sitcom #bbbgshow #funny #comedy",
    },
    {
        "index": 68,
        "id": "4gV3UtFkSAQ",
        "title": "Sheldon is a blabbermouth.🤣 #sitcom #bbbgshow #funny #movie #comedy",
    },
    {
        "index": 69,
        "id": "-V8vjW9KA9I",
        "title": "Sheldon hires Professor Proton for home science experiments.🤣#sitcom #comedy #tvshow #bbnow",
    },
    {
        "index": 70,
        "id": "S5XwlAnSsQA",
        "title": "Sheldon’s words make Leonard uneasy.😂 #sitcom #bbbgshow #funny #comedy #movie",
    },
    {
        "index": 71,
        "id": "Tgy2St0YgeA",
        "title": "Penny gets jealous of Leonard.🤣 #sitcom #bbbgshow #funny #movie #comedy",
    },
    {
        "index": 72,
        "id": "yEIillQd480",
        "title": "Amy helps Sheldon treat his need for closure.🤣 #sitcom #bbbgshow #funny #movie #comedy",
    },
    {
        "index": 73,
        "id": "t4qZezt-OAY",
        "title": "Sheldon starts an intimate game with Amy.🤣 #sitcom #bbbgshow #funny #movie #comedy",
    },
    {
        "index": 74,
        "id": "UTmoaVerwqs",
        "title": "Sheldon tries hard to stop Leonard from going away for work.😂 #sitcom #bbbgshow #funny #movie#comedy",
    },
]


def sanitize_title(title: str) -> str:
    clean = re.sub(r'#\S+', '', title).strip()
    clean = re.sub(r'\s+', ' ', clean)
    clean = re.sub(r'[\\/*?:"<>|]', '', clean)
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


def get_video_duration(video_path: Path) -> float:
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(video_path)]
    p = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(json.loads(p.stdout)['format']['duration'])


def split_video(src_path: Path, p1_path: Path, p2_path: Path, split_sec: float):
    # Part 1: 0 to split_sec
    cmd1 = ['ffmpeg', '-y', '-ss', '0', '-to', str(round(split_sec, 2)), '-i', str(src_path), '-c', 'copy', str(p1_path)]
    subprocess.run(cmd1, capture_output=True, check=True)

    # Part 2: split_sec to end
    cmd2 = ['ffmpeg', '-y', '-ss', str(round(split_sec, 2)), '-i', str(src_path), '-c', 'copy', str(p2_path)]
    subprocess.run(cmd2, capture_output=True, check=True)


def build_split_caption(clean_title: str, part: int) -> str:
    tags = "#thebigbangtheory #tbbt #sheldoncooper #bazinga #pennyandleonard #shamy #reels #reelsinstagram #comedyreels #sitcom #funnyreels #viralreels #explorepage #sitcomvaultdaily"
    if part == 1:
        return (
            f"[PART 1/2] {clean_title} 😂🍿\n\n"
            f"Sheldon is at it again! Wait until you see how this plays out in Part 2! 🤣\n\n"
            f"💬 Part 2 drops tomorrow! What do you think happens next? Tell us below! 👇\n\n"
            f"👉 Follow @sitcomvaultdaily for daily Big Bang Theory & comedy gold! 🍿\n"
            f"Double-tap if this made your day! ❤️\n\n"
            f"•\n•\n•\n"
            f"{tags}"
        )
    else:
        return (
            f"[PART 2/2] {clean_title} 🤣💥\n\n"
            f"The conclusion you've been waiting for! Nobody delivers punchlines like Sheldon Cooper. 😂\n\n"
            f"💬 Did you see that coming? Rate this scene from 1 to 10 below! 👇\n\n"
            f"👉 Follow @sitcomvaultdaily for daily Big Bang Theory & comedy gold! 🍿\n"
            f"Double-tap if you love sitcoms! ❤️\n\n"
            f"•\n•\n•\n"
            f"{tags}"
        )


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    REELS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("  DOWNLOADING & PROCESSING 9 NEW SHORTS FROM @diepvo8265")
    print("=" * 65)

    downloaded_items = []
    
    # 1. Download raw videos
    for item in NEW_SHORTS:
        idx = item["index"]
        vid_id = item["id"]
        raw_title = item["title"]
        clean_t = sanitize_title(raw_title)
        
        filename = f"diepvo8265_{idx:02d}_{clean_t}.mp4"
        filepath = RAW_DIR / filename
        
        print(f"\n[{idx}/74] Processing: {clean_t}")
        print(f"      Video ID: {vid_id}")
        
        if filepath.exists() and filepath.stat().st_size > 500_000:
            print(f"      Cached already: {filepath.name} ({filepath.stat().st_size / (1024*1024):.1f} MB)")
        else:
            print(f"      Downloading from YouTube...")
            dl_opts = {
                "outtmpl": str(filepath),
                "format": "136+140/398+140/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "quiet": True,
                "no_warnings": True,
                "overwrites": True,
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                }
            }
            with yt_dlp.YoutubeDL(dl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/shorts/{vid_id}"])
            print(f"      Downloaded: {filepath.name} ({filepath.stat().st_size / (1024*1024):.1f} MB)")
            time.sleep(1)

        # Thumbnail for raw
        extract_thumbnail(filepath)
        
        # Duration check
        dur = get_video_duration(filepath)
        split_point = dur / 2.0
        print(f"      Duration: {dur:.1f}s -> Splitting into two parts @ {split_point:.1f}s each")
        
        # 2. Split into Part 1 and Part 2
        p1_name = f"diepvo8265_{idx:02d}_part1_{clean_t}.mp4"
        p2_name = f"diepvo8265_{idx:02d}_part2_{clean_t}.mp4"
        p1_path = REELS_DIR / p1_name
        p2_path = REELS_DIR / p2_name
        
        if not p1_path.exists() or not p2_path.exists():
            split_video(filepath, p1_path, p2_path, split_point)
            print(f"      Created Part 1: {p1_name} ({p1_path.stat().st_size / (1024*1024):.1f} MB)")
            print(f"      Created Part 2: {p2_name} ({p2_path.stat().st_size / (1024*1024):.1f} MB)")
        else:
            print(f"      Parts already exist in {REELS_DIR.name}")
            
        extract_thumbnail(p1_path)
        extract_thumbnail(p2_path)
        
        downloaded_items.append({
            "index": idx,
            "id": vid_id,
            "title": raw_title,
            "clean_title": clean_t,
            "raw_file": str(filepath),
            "p1_file": str(p1_path),
            "p2_file": str(p2_path),
            "p1_name": p1_name,
            "p2_name": p2_name,
            "duration": dur
        })

    # 3. Update Manifest
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        
        existing_ids = {s.get("id") or s.get("youtube_id") for s in manifest_data.get("shorts", [])}
        for d in downloaded_items:
            if d["id"] not in existing_ids:
                manifest_data["shorts"].append({
                    "id": d["id"],
                    "sequence": d["index"],
                    "title": d["title"],
                    "clean_title": d["clean_title"],
                    "local_path": d["raw_file"],
                    "file_name": Path(d["raw_file"]).name,
                    "file_size_mb": round(Path(d["raw_file"]).stat().st_size / (1024*1024), 2),
                    "url": f"https://www.youtube.com/shorts/{d['id']}"
                })
        manifest_data["total_shorts"] = len(manifest_data["shorts"])
        manifest_data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Updated manifest: {MANIFEST_PATH} (now {manifest_data['total_shorts']} shorts)")

    # 4. Append to instagram_queue.json
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            queue_data = json.load(f)

        existing_queue_ids = {item.get("id") for item in queue_data.get("queue", [])}
        current_len = len(queue_data.get("queue", []))

        # Determine start date after last item
        last_item = queue_data["queue"][-1] if queue_data.get("queue") else None
        if last_item and last_item.get("scheduled_for"):
            last_date_str = last_item["scheduled_for"].split()[0]
            start_date = datetime.strptime(last_date_str, "%Y-%m-%d") + timedelta(days=1)
        else:
            start_date = datetime.now() + timedelta(days=1)

        added_count = 0
        new_items = []
        for d in downloaded_items:
            for part in [1, 2]:
                part_id = f"{d['id']}_p{part}"
                if part_id in existing_queue_ids:
                    continue

                sched_dt = start_date + timedelta(days=added_count)
                sched_str = sched_dt.strftime("%Y-%m-%d 19:30")
                part_file = d["p1_file"] if part == 1 else d["p2_file"]
                part_name = d["p1_name"] if part == 1 else d["p2_name"]

                queue_item = {
                    "queue_index": current_len + added_count + 1,
                    "id": part_id,
                    "show": "The Big Bang Theory",
                    "local_path": part_file,
                    "file_name": part_name,
                    "title": f"[Part {part}] {d['clean_title']}.🤣",
                    "caption": build_split_caption(d["clean_title"], part),
                    "status": "pending",
                    "scheduled_for": sched_str,
                    "instagram_media_id": None,
                    "instagram_code": None,
                    "instagram_url": None,
                    "posted_at": None
                }
                new_items.append(queue_item)
                added_count += 1

        if new_items:
            queue_data["queue"].extend(new_items)
            queue_data["total_items"] = len(queue_data["queue"])
            queue_data["pending_items"] = sum(1 for x in queue_data["queue"] if not x.get("instagram_media_id"))
            queue_data["posted_items"] = sum(1 for x in queue_data["queue"] if x.get("instagram_media_id"))
            queue_data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(queue_data, f, indent=2, ensure_ascii=False)
            print(f"[OK] Appended {len(new_items)} new Reels to queue: {QUEUE_FILE}")
            print(f"     Total items: {queue_data['total_items']} | Pending: {queue_data['pending_items']} | Posted: {queue_data['posted_items']}")

    print("\n" + "=" * 65)
    print("           ALL 9 NEW SHORTS SUCCESSFULLY DOWNLOADED & PROCESSED!")
    print("=" * 65)


if __name__ == "__main__":
    main()
