"""
Uploads and schedules the 15 Just Nature shorts to YouTube using config/token_just_nature.json.
Category 19 = Travel & Events.
"""
import os
import sys
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import time
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly"
]

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
TOKEN_FILE = CONFIG_DIR / "token_just_nature.json"
QUEUE_FILE = Path(r"D:\Media\shorts\just_nature\upload_queue.json")
PROGRESS_FILE = Path(r"D:\Media\shorts\just_nature\upload_progress.json")

def get_service():
    if not TOKEN_FILE.exists():
        print(f"[ERROR] Token file not found: {TOKEN_FILE}")
        print("Please run first:")
        print("python scripts/auth_youtube_channel.py --token config/token_just_nature.json")
        sys.exit(1)
        
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            for attempt in range(5):
                try:
                    creds.refresh(Request())
                    TOKEN_FILE.write_text(creds.to_json())
                    break
                except Exception as e:
                    if attempt < 4:
                        print(f"Token refresh attempt {attempt+1} failed: {e}. Retrying in 3s...")
                        time.sleep(3)
                    else:
                        print(f"[ERROR] Could not refresh credentials after 5 attempts: {e}")
                        sys.exit(1)
        else:
            print("[ERROR] Credentials invalid or expired. Re-authenticate via auth_youtube_channel.py.")
            sys.exit(1)
            
    return build("youtube", "v3", credentials=creds)

def main():
    if not QUEUE_FILE.exists():
        print(f"[ERROR] Queue file not found: {QUEUE_FILE}")
        sys.exit(1)

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    # Load progress if any
    progress = {}
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress = json.load(f)
        except Exception:
            pass

    youtube = get_service()

    # Verify channel identity
    try:
        ch_resp = youtube.channels().list(part="snippet,statistics", mine=True).execute()
        ch = ch_resp.get("items", [])[0]
        print(f"Logged in as: {ch['snippet']['title']} ({ch['snippet'].get('customUrl', '')})")
    except Exception as e:
        print(f"Warning verifying channel: {e}")

    print(f"\nTotal items in queue: {len(queue)}")
    
    for item in queue:
        fn = item["filename"]
        if fn in progress and progress[fn].get("status") == "success":
            print(f"[-] Already uploaded: {fn} -> {progress[fn]['youtube_url']}")
            continue

        video_path = item["filepath"]
        if not os.path.exists(video_path):
            print(f"[!] File not found: {video_path}")
            continue

        print(f"\n[+] Uploading: {item['title']} ({fn})")
        print(f"    Scheduled for: {item['scheduled_time']}")

        body = {
            "snippet": {
                "title": item["title"],
                "description": item["description"],
                "tags": item["tags"],
                "categoryId": "19", # Travel & Events
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
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

            response = None
            while response is None:
                status_prog, response = request.next_chunk()
                if status_prog:
                    print(f"    Progress: {int(status_prog.progress() * 100)}%")

            vid_id = response["id"]
            yt_url = f"https://www.youtube.com/shorts/{vid_id}"
            print(f"    [DONE] Video ID: {vid_id} -> {yt_url}")

            progress[fn] = {
                "status": "success",
                "video_id": vid_id,
                "youtube_url": yt_url,
                "scheduled_time": item["scheduled_time"]
            }

            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(progress, f, indent=2)

            time.sleep(2)
        except Exception as err:
            err_str = str(err)
            print(f"\n[!] Upload error for {fn}: {err}")
            if "uploadLimitExceeded" in err_str or "quotaExceeded" in err_str:
                print("\n[NOTICE] YouTube API daily upload quota reached.")
                print("Options:")
                print("1. Wait for quota reset (midnight Pacific Time).")
                print("2. Or drag-and-drop the remaining videos directly in YouTube Studio, and we can auto-update their titles/descriptions via script!")
                break
            else:
                progress[fn] = {"status": "failed", "error": err_str}
                with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                    json.dump(progress, f, indent=2)

    print("\nAll pending shorts scheduled successfully!")

if __name__ == "__main__":
    main()
