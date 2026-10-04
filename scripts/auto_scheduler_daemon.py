"""
Continuous scheduler daemon for Just Nature YouTube Shorts.
Polls YouTube API. As soon as the daily quota resets (12:30 PM IST),
it immediately uploads and schedules the pending shorts in the queue.
"""
import sys
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import time
import json
from datetime import datetime
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT_DIR = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT_DIR / "config" / "token_just_nature.json"
QUEUE_FILE = Path(r"D:\Media\shorts\just_nature\upload_queue.json")
PROGRESS_FILE = Path(r"D:\Media\shorts\just_nature\upload_progress.json")
LOG_FILE = Path(r"D:\Media\shorts\just_nature\youtube_upload.log")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly"
]

def log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def get_service():
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            for attempt in range(5):
                try:
                    creds.refresh(Request())
                    TOKEN_FILE.write_text(creds.to_json())
                    break
                except Exception as e:
                    time.sleep(3)
    return build("youtube", "v3", credentials=creds)

def attempt_upload_batch():
    if not QUEUE_FILE.exists():
        log("[ERROR] Queue file not found.")
        return False, "no_queue"

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    progress = {}
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress = json.load(f)
        except Exception:
            pass

    youtube = get_service()
    uploaded_this_run = 0

    for item in queue:
        fn = item["filename"]
        if fn in progress and progress[fn].get("status") == "success":
            continue

        video_path = item["filepath"]
        if not os.path.exists(video_path):
            log(f"[SKIP] Video file not found: {video_path}")
            continue

        log(f"Attempting upload: {item['title']} ({fn}) for {item['scheduled_time']}")

        body = {
            "snippet": {
                "title": item["title"][:100],
                "description": item["description"],
                "tags": item["tags"],
                "categoryId": "19",
                "defaultLanguage": "en"
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": item["scheduled_time"],
                "selfDeclaredMadeForKids": False
            }
        }

        try:
            media = MediaFileUpload(video_path, chunksize=1024*1024*4, resumable=True, mimetype="video/mp4")
            req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

            response = None
            while response is None:
                status_prog, response = req.next_chunk()
                if status_prog:
                    log(f"  Uploading {fn}: {int(status_prog.progress() * 100)}%")

            vid_id = response["id"]
            yt_url = f"https://www.youtube.com/shorts/{vid_id}"
            log(f"[SUCCESS] Scheduled {fn} -> {yt_url}")

            progress[fn] = {
                "status": "success",
                "video_id": vid_id,
                "youtube_url": yt_url,
                "scheduled_time": item["scheduled_time"]
            }
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(progress, f, indent=2)

            uploaded_this_run += 1
            time.sleep(3)

            # Max 10 per day
            if uploaded_this_run >= 10:
                log(f"Reached 10 uploads in this batch. Done for today.")
                return True, "batch_complete"

        except Exception as err:
            err_str = str(err)
            if "uploadLimitExceeded" in err_str or "quotaExceeded" in err_str:
                log(f"[LOCKED] YouTube upload quota still active: {err}")
                return False, "quota_locked"
            else:
                log(f"[ERROR] Upload error for {fn}: {err}")
                progress[fn] = {"status": "failed", "error": err_str}
                with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                    json.dump(progress, f, indent=2)

    return True, "all_done"

def main():
    log("Starting Just Nature Auto-Scheduler Daemon...")
    while True:
        success, reason = attempt_upload_batch()
        if success:
            log(f"Upload batch finished successfully ({reason}). Sleeping until next daily cycle.")
            time.sleep(3600 * 6) # Sleep 6 hours
        else:
            log(f"Upload locked ({reason}). Retrying in 10 minutes...")
            time.sleep(600) # Sleep 10 minutes

if __name__ == "__main__":
    main()
