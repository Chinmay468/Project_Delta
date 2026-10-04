import sys
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

SWITZERLAND_DIR = Path(r"D:\Media\shorts\just_nature")
NORWAY_DIR = Path(r"D:\Media\shorts\just_nature\norway")

SWITZERLAND_MEGA = "https://mega.nz/folder/DoJ10CxR#vJFcifmagnt5g1tmFopEfA"
NORWAY_MEGA = "https://mega.nz/folder/D5BHwCyD#ccLQOk7CzMsnlN85CtHq_g"

# Load Switzerland queue and progress
with open(SWITZERLAND_DIR / "upload_queue.json", "r", encoding="utf-8") as f:
    sw_queue = json.load(f)

sw_progress = {}
if (SWITZERLAND_DIR / "upload_progress.json").exists():
    with open(SWITZERLAND_DIR / "upload_progress.json", "r", encoding="utf-8") as f:
        sw_progress = json.load(f)

# Load Norway queue
with open(NORWAY_DIR / "upload_queue.json", "r", encoding="utf-8") as f:
    no_queue = json.load(f)

combined_queue = []
item_index = 1

# Process Switzerland items (Oct 4 - Oct 31)
for item in sw_queue:
    fn = item["filename"]
    is_posted = fn in sw_progress and sw_progress[fn].get("status") == "success"
    
    # Check if scheduled on YouTube Studio already
    yt_id = sw_progress[fn].get("video_id") if is_posted else None
    yt_url = sw_progress[fn].get("youtube_url") if is_posted else None
    
    combined_queue.append({
        "index": item_index,
        "region": "Switzerland",
        "month": "October 2026",
        "filename": fn,
        "mega_folder": SWITZERLAND_MEGA,
        "title": item["title"],
        "description": item["description"],
        "tags": item["tags"],
        "pillar": item.get("pillar", "Swiss Landscapes"),
        "scheduled_time": item["scheduled_time"],
        "status": "posted" if is_posted else "pending",
        "youtube_id": yt_id,
        "youtube_url": yt_url
    })
    item_index += 1

# Process Norway items (Nov 1 - Nov 30)
for item in no_queue:
    fn = item["filename"]
    combined_queue.append({
        "index": item_index,
        "region": "Norway",
        "month": "November 2026",
        "filename": fn,
        "mega_folder": NORWAY_MEGA,
        "title": item["title"],
        "description": item["description"],
        "tags": item["tags"],
        "pillar": item.get("pillar", "Norway Nature"),
        "scheduled_time": item["scheduled_time"],
        "status": "pending",
        "youtube_id": None,
        "youtube_url": None
    })
    item_index += 1

total_posted = sum(1 for q in combined_queue if q["status"] == "posted")
total_pending = sum(1 for q in combined_queue if q["status"] == "pending")

queue_data = {
    "channel": "@just.nature46",
    "channel_id": "UC_q-3rJiSjslro_sIUUNI4jA",
    "total_items": len(combined_queue),
    "posted_items": total_posted,
    "pending_items": total_pending,
    "queue": combined_queue
}

output_path = DATA_DIR / "just_nature_queue.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(queue_data, f, indent=2, ensure_ascii=False)

print(f"Built data/just_nature_queue.json:")
print(f"  Total items: {len(combined_queue)}")
print(f"  Posted items (already on YouTube): {total_posted}")
print(f"  Pending items to publish: {total_pending}")
print(f"  Covering: Switzerland (Oct 4-31) and Norway (Nov 1-30)")
