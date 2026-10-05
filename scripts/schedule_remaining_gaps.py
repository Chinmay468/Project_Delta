import sys
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import time
from pathlib import Path
from datetime import datetime
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

TASKS = [
    {
        "index": 12,
        "publish_at": "2026-10-07T18:00:00Z",
        "video_filename": "just_nature_14_zermatt_matterhorn_sunrise.mp4",
        "thumb_filename": "just_nature_14_zermatt_matterhorn_sunrise_thumb.jpg",
    },
    {
        "index": 8,
        "publish_at": "2026-10-08T18:00:00Z",
        "video_filename": "just_nature_08_valle_verzasca_emerald_paradise.mp4",
        "thumb_filename": "just_nature_08_valle_verzasca_emerald_paradise_thumb.jpg",
    },
    {
        "index": 13,
        "publish_at": "2026-10-11T18:00:00Z",
        "video_filename": "just_nature_15_wengen_fairytale_alpine_village.mp4",
        "thumb_filename": "just_nature_15_wengen_fairytale_alpine_village_thumb.jpg",
    },
    {
        "index": 16,
        "publish_at": "2026-10-13T18:00:00Z",
        "video_filename": "just_nature_18_grindelwald_first_cliff_walk.mp4",
        "thumb_filename": "just_nature_18_grindelwald_first_cliff_walk_thumb.jpg",
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

    # First update Index 11 which was already uploaded (O_23BL2I1OU)
    item_11 = next(x for x in q_data["queue"] if x["index"] == 11)
    item_11["youtube_id"] = "O_23BL2I1OU"
    item_11["youtube_url"] = "https://www.youtube.com/shorts/O_23BL2I1OU"
    item_11["scheduled_time"] = "2026-10-06T18:00:00Z"
    item_11["status"] = "posted"

    media_dir = Path(r"D:\Media\shorts\just_nature")

    for task in TASKS:
        idx = task["index"]
        publish_at = task["publish_at"]
        video_path = media_dir / task["video_filename"]
        thumb_path = media_dir / task["thumb_filename"]

        item = next(x for x in q_data["queue"] if x["index"] == idx)

        print(f"\n==================================================")
        print(f"[START UPLOAD #{idx}] {item['title']}")
        print(f"File:         {video_path} ({video_path.stat().st_size / (1024*1024):.2f} MB)")
        print(f"Publish At:   {publish_at}")

        body = {
            "snippet": {
                "title": item["title"][:100],
                "description": item.get("description", ""),
                "tags": item.get("tags", []),
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
            print(f"[SUCCESS] #{idx} uploaded! Video ID: {vid_id} | URL: {yt_url}")

            # Thumbnail
            if thumb_path.exists():
                try:
                    youtube.thumbnails().set(
                        videoId=vid_id,
                        media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg")
                    ).execute()
                    print("  [THUMBNAIL] Applied successfully.")
                except Exception as t_err:
                    print(f"  [THUMBNAIL] Note: skipped ({t_err})")

            # Update queue record
            item["youtube_id"] = vid_id
            item["youtube_url"] = yt_url
            item["scheduled_time"] = publish_at
            item["status"] = "posted"

            # Telegram alert
            try:
                telegram_notifier.notify_published(
                    platform="YouTube",
                    channel="Just Nature (@just.nature46)",
                    title=f"Scheduled: {item['title']}",
                    url=yt_url,
                    queue_index=idx,
                    extra_info=f"Scheduled for {publish_at}"
                )
            except Exception as tel_err:
                print(f"  [TELEGRAM] Note: skipped ({tel_err})")

            # Save queue after each successful upload
            with open(QUEUE_FILE, "w", encoding="utf-8") as f_out:
                json.dump(q_data, f_out, indent=2, ensure_ascii=False)

            # Polite pause between uploads
            time.sleep(3)

        except Exception as e:
            print(f"[ERROR] Failed to upload #{idx}: {e}")
            break

    # Update summary counts
    q_data["posted_items"] = sum(1 for q in q_data["queue"] if q.get("status") == "posted")
    q_data["pending_items"] = sum(1 for q in q_data["queue"] if q.get("status") == "pending")
    with open(QUEUE_FILE, "w", encoding="utf-8") as f_out:
        json.dump(q_data, f_out, indent=2, ensure_ascii=False)

    print("\n[ALL TASKS FINISHED] Queue updated successfully.")

if __name__ == "__main__":
    main()
