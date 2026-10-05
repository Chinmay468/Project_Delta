import json
from pathlib import Path

QUEUE_FILE = Path("data/just_nature_queue.json")
with open(QUEUE_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

existing_names = [q.get("filename") for q in data["queue"]]
if "04_red_funicular_green_meadows.mp4" not in existing_names:
    new_entry = {
        "index": len(data["queue"]) + 1,
        "region": "Switzerland",
        "filename": "04_red_funicular_green_meadows.mp4",
        "local_path": r"D:\Media\shorts\just_nature\from_instagram\04_red_funicular_green_meadows.mp4",
        "title": "Red Funicular Gliding Down the Swiss Mountain Slopes 🚞💚",
        "description": "Red Funicular Gliding Down the Swiss Mountain Slopes 🚞💚\n\nFirst-person view of a bright red mountain funicular descending steep green Swiss hills overlooking chalets and jagged peaks.\n\n📍 Location: Swiss Alps, Switzerland\n🏔️ Category: Scenic Swiss Funiculars\n\nWelcome to Just Nature (@Just.Nature46)! We bring you the most breathtaking landscapes, scenic train journeys, and peaceful nature views from Switzerland and around the world.\n\n✨ Subscribe to @Just.Nature46 for daily wanderlust & nature relaxation!\n❤️ Like, save, and share this with someone who needs to see this view!\n\n#switzerland #nature #travel #swissalps #shorts #funicular #swisstrain #cablecar #greenpastures #wanderlust #landscape #4knature",
        "tags": ["switzerland", "nature", "travel", "swissalps", "shorts", "funicular", "swisstrain", "cablecar", "greenpastures", "wanderlust", "landscape"],
        "pillar": "Swiss Highlights from Instagram",
        "scheduled_time": "2026-10-13T18:00:00Z",
        "status": "pending",
        "youtube_id": None,
        "youtube_url": None
    }
    data["queue"].append(new_entry)

data["posted_items"] = sum(1 for q in data["queue"] if q.get("status") == "posted")
data["pending_items"] = sum(1 for q in data["queue"] if q.get("status") == "pending")
data["total_items"] = len(data["queue"])

with open(QUEUE_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Queue updated: total={data['total_items']}, posted={data['posted_items']}, pending={data['pending_items']}")
