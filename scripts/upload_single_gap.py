import sys
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
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

    # Target: Lauterbrunnen Aerial View
    video_path = Path(r"D:\Media\shorts\just_nature\just_nature_13_lauterbrunnen_aerial_drone.mp4")
    thumb_path = Path(r"D:\Media\shorts\just_nature\just_nature_13_lauterbrunnen_aerial_drone_thumb.jpg")
    publish_at = "2026-10-06T18:00:00Z" # 11:30 PM IST tonight

    # Load item from queue
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        q_data = json.load(f)

    item = next(x for x in q_data["queue"] if x["index"] == 11)

    print(f"\n[UPLOAD START]")
    print(f"Title:        {item['title']}")
    print(f"File:         {video_path} ({video_path.stat().st_size / (1024*1024):.2f} MB)")
    print(f"Schedule:     {publish_at} (11:30 PM IST tonight)")

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

    media = MediaFileUpload(str(video_path), chunksize=1024*1024*4, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Progress: {int(status.progress() * 100)}%")

    vid_id = response["id"]
    yt_url = f"https://www.youtube.com/shorts/{vid_id}"
    print(f"\n[SUCCESS] Uploaded and scheduled on YouTube!")
    print(f"Video ID:     {vid_id}")
    print(f"URL:          {yt_url}")
    print(f"Scheduled At: {publish_at}")

    # Set thumbnail if possible
    if thumb_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=vid_id,
                media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg")
            ).execute()
            print("[THUMBNAIL] Custom thumbnail applied successfully.")
        except Exception as e:
            print(f"[THUMBNAIL] Note: could not set custom thumbnail ({e})")

    # Send Telegram notification
    try:
        telegram_notifier.notify_published(
            platform="YouTube",
            channel="Just Nature (@just.nature46)",
            title=f"Scheduled: {item['title']}",
            url=yt_url,
            queue_index=11,
            extra_info=f"Scheduled for {publish_at} (11:30 PM IST)"
        )
    except Exception as tel_err:
        print(f"[TELEGRAM] Note: ping skipped ({tel_err})")

if __name__ == "__main__":
    main()
