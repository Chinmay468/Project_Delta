import sys
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import time
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import telegram_notifier

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
TOKEN_FILE = CONFIG_DIR / "token_just_nature.json"
DATA_DIR = ROOT / "data"
QUEUE_FILE = DATA_DIR / "just_nature_queue.json"

MEDIA_DIR = Path(r"D:\Media\shorts\just_nature\from_instagram")

REELS_TO_SCHEDULE = [
    {
        "slot_date": "2026-10-06T18:00:00Z", # Tonight
        "video_file": "01_aare_gorge_switzerland.mp4",
        "thumb_file": "01_aare_gorge_switzerland_thumb.jpg",
        "title": "Aare Gorge: Switzerland's Crystalline Glacial Canyon 🇨🇭🌊",
        "description": "Aare Gorge: Switzerland's Crystalline Glacial Canyon 🇨🇭🌊\n\nGliding through the dramatic 200-meter sheer limestone gorge of Aareschlucht in Meiringen over milky turquoise glacial waters.\n\n📍 Location: Aareschlucht, Meiringen, Switzerland\n🏔️ Category: Turquoise Alpine Waters & Gorges\n\nWelcome to Just Nature (@Just.Nature46)! We bring you the most breathtaking landscapes, scenic train journeys, and peaceful nature views from Switzerland and around the world.\n\n✨ Subscribe to @Just.Nature46 for daily wanderlust & nature relaxation!\n❤️ Like, save, and share this with someone who needs to see this view!\n\n#switzerland #nature #travel #swissalps #shorts #aareschlucht #aaregorge #meiringen #canyon #emeraldwater #wanderlust #landscape #4knature",
        "tags": ["switzerland", "nature", "travel", "swissalps", "shorts", "aareschlucht", "aaregorge", "meiringen", "canyon", "emeraldwater", "wanderlust", "landscape"]
    },
    {
        "slot_date": "2026-10-07T18:00:00Z", # Tomorrow
        "video_file": "02_swiss_alpine_valley_mist.mp4",
        "thumb_file": "02_swiss_alpine_valley_mist_thumb.jpg",
        "title": "Swiss Alpine Valley in Autumn Mist 🏔️☁️",
        "description": "Swiss Alpine Valley in Autumn Mist 🏔️☁️\n\nGolden autumn meadows, gentle valley clouds drifting through pine trees, and snow-dusted alpine summits in the Swiss Alps.\n\n📍 Location: Bernese Oberland, Switzerland\n🏔️ Category: Fairytale Alpine Valleys\n\nWelcome to Just Nature (@Just.Nature46)! We bring you the most breathtaking landscapes, scenic train journeys, and peaceful nature views from Switzerland and around the world.\n\n✨ Subscribe to @Just.Nature46 for daily wanderlust & nature relaxation!\n❤️ Like, save, and share this with someone who needs to see this view!\n\n#switzerland #nature #travel #swissalps #shorts #autumnvibes #mountainmist #berneseoberland #clouds #wanderlust #landscape #4knature",
        "tags": ["switzerland", "nature", "travel", "swissalps", "shorts", "autumnvibes", "mountainmist", "berneseoberland", "clouds", "wanderlust", "landscape"]
    },
    {
        "slot_date": "2026-10-11T18:00:00Z", # Sunday
        "video_file": "03_glacial_river_swiss_peaks.mp4",
        "thumb_file": "03_glacial_river_swiss_peaks_thumb.jpg",
        "title": "Glacial River Flowing Beneath the Swiss Alps 🌿🏔️",
        "description": "Glacial River Flowing Beneath the Swiss Alps 🌿🏔️\n\nRushing crystal turquoise river flowing through lush green pastures with traditional chalets and a massive sunlit rock face.\n\n📍 Location: Swiss Alps, Switzerland\n🏔️ Category: Turquoise Alpine Waters\n\nWelcome to Just Nature (@Just.Nature46)! We bring you the most breathtaking landscapes, scenic train journeys, and peaceful nature views from Switzerland and around the world.\n\n✨ Subscribe to @Just.Nature46 for daily wanderlust & nature relaxation!\n❤️ Like, save, and share this with someone who needs to see this view!\n\n#switzerland #nature #travel #swissalps #shorts #glacialriver #mountainriver #swissviews #naturetherapy #wanderlust #landscape #4knature",
        "tags": ["switzerland", "nature", "travel", "swissalps", "shorts", "glacialriver", "mountainriver", "swissviews", "naturetherapy", "wanderlust", "landscape"]
    },
    {
        "slot_date": "2026-10-13T18:00:00Z", # Tuesday
        "video_file": "04_red_funicular_green_meadows.mp4",
        "thumb_file": "04_red_funicular_green_meadows_thumb.jpg",
        "title": "Red Funicular Gliding Down the Swiss Mountain Slopes 🚞💚",
        "description": "Red Funicular Gliding Down the Swiss Mountain Slopes 🚞💚\n\nFirst-person view of a bright red mountain funicular descending steep green Swiss hills overlooking chalets and jagged peaks.\n\n📍 Location: Swiss Alps, Switzerland\n🏔️ Category: Scenic Swiss Funiculars\n\nWelcome to Just Nature (@Just.Nature46)! We bring you the most breathtaking landscapes, scenic train journeys, and peaceful nature views from Switzerland and around the world.\n\n✨ Subscribe to @Just.Nature46 for daily wanderlust & nature relaxation!\n❤️ Like, save, and share this with someone who needs to see this view!\n\n#switzerland #nature #travel #swissalps #shorts #funicular #swisstrain #cablecar #greenpastures #wanderlust #landscape #4knature",
        "tags": ["switzerland", "nature", "travel", "swissalps", "shorts", "funicular", "swisstrain", "cablecar", "greenpastures", "wanderlust", "landscape"]
    }
]

def get_youtube():
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
        else:
            raise RuntimeError("Credentials invalid and no refresh token.")
    return build("youtube", "v3", credentials=creds)

def main():
    youtube = get_youtube()
    print("[AUTH] Successfully connected to YouTube API as Just Nature.")

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        q_data = json.load(f)

    for item_spec in REELS_TO_SCHEDULE:
        video_path = MEDIA_DIR / item_spec["video_file"]
        thumb_path = MEDIA_DIR / item_spec["thumb_file"]
        publish_at = item_spec["slot_date"]
        title = item_spec["title"]

        print(f"\n==================================================")
        print(f"[START UPLOAD] {title}")
        print(f"File:       {video_path} ({video_path.stat().st_size / (1024*1024):.2f} MB)")
        print(f"Publish At: {publish_at}")

        body = {
            "snippet": {
                "title": title[:100],
                "description": item_spec["description"],
                "tags": item_spec["tags"],
                "categoryId": "19", # Travel & Events
                "defaultLanguage": "en"
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": publish_at,
                "selfDeclaredMadeForKids": False
            }
        }

        try:
            media = MediaFileUpload(str(video_path), chunksize=1024*1024*4, resumable=True, mimetype="video/mp4")
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"  Uploading: {int(status.progress() * 100)}%", flush=True)

            vid_id = response["id"]
            yt_url = f"https://www.youtube.com/shorts/{vid_id}"
            print(f"[SUCCESS] Uploaded! Video ID: {vid_id} | URL: {yt_url}")

            # Apply thumbnail
            if thumb_path.exists():
                try:
                    youtube.thumbnails().set(
                        videoId=vid_id,
                        media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg")
                    ).execute()
                    print("  [THUMBNAIL] Applied successfully.")
                except Exception as t_err:
                    print(f"  [THUMBNAIL] Note: skipped ({t_err})")

            # Update queue
            new_entry = {
                "index": len(q_data["queue"]) + 1,
                "region": "Switzerland",
                "filename": item_spec["video_file"],
                "local_path": str(video_path),
                "title": title,
                "description": item_spec["description"],
                "tags": item_spec["tags"],
                "pillar": "Swiss Highlights from Instagram",
                "scheduled_time": publish_at,
                "status": "posted",
                "youtube_id": vid_id,
                "youtube_url": yt_url
            }
            q_data["queue"].append(new_entry)
            q_data["posted_items"] = sum(1 for q in q_data["queue"] if q.get("status") == "posted")
            q_data["pending_items"] = sum(1 for q in q_data["queue"] if q.get("status") == "pending")

            with open(QUEUE_FILE, "w", encoding="utf-8") as f_out:
                json.dump(q_data, f_out, indent=2, ensure_ascii=False)

            # Telegram alert
            try:
                telegram_notifier.notify_published(
                    platform="YouTube",
                    channel="Just Nature (@just.nature46)",
                    title=f"Scheduled: {title}",
                    url=yt_url,
                    queue_index=new_entry["index"],
                    extra_info=f"Scheduled for {publish_at} (From Instagram)"
                )
            except Exception as tel_err:
                print(f"  [TELEGRAM] Note: skipped ({tel_err})")

            time.sleep(3)

        except Exception as e:
            print(f"[ERROR] Failed to upload {title}: {e}")
            break

    print("\n[ALL DONE] Queue synchronization completed.")

if __name__ == "__main__":
    main()
