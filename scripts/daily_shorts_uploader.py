"""
Daily YouTube Shorts Uploader & Queue Scheduler
================================================
Manages daily uploading of downloaded YouTube shorts from D:\\Media\\shorts\\diepvo8265\\
Features:
- Generates/maintains an upload queue (upload_queue.json) with optimized SEO titles & tags.
- Verifies OAuth 2.0 authorization with YouTube Data API v3 and displays channel info.
- Uploads the next scheduled short in the queue (or a specific slot).
- Supports both immediate public release and scheduled release (publishAt).
- Can configure Windows Task Scheduler to run daily hands-free.
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

# Force UTF-8 on Windows console for emoji support
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CLIENT_SECRET_FILE = CONFIG_DIR / "client_secret.json"
TOKEN_FILE = CONFIG_DIR / "token.json"

SHORTS_DIR = Path(r"D:\Media\shorts\diepvo8265")
MANIFEST_FILE = SHORTS_DIR / "manifest.json"
QUEUE_FILE = SHORTS_DIR / "upload_queue.json"


def get_authenticated_service():
    """Authenticates using OAuth 2.0 and returns the YouTube API service."""
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[AUTH] Refreshing expired OAuth credentials...")
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_FILE.exists():
                print(f"[AUTH ERROR] {CLIENT_SECRET_FILE} not found. Place OAuth client_secret.json in config/.")
                sys.exit(1)
            print("[AUTH] Opening browser for YouTube OAuth authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        print(f"[AUTH] Saved authorization token to {TOKEN_FILE}")

    return build("youtube", "v3", credentials=creds)


def get_channel_info(youtube):
    """Fetches details of the authenticated YouTube channel."""
    try:
        response = youtube.channels().list(mine=True, part="snippet,statistics").execute()
        items = response.get("items", [])
        if not items:
            return None
        item = items[0]
        return {
            "id": item["id"],
            "title": item["snippet"]["title"],
            "handle": item["snippet"].get("customUrl", ""),
            "subscribers": item.get("statistics", {}).get("subscriberCount", "Hidden"),
            "videos": item.get("statistics", {}).get("videoCount", "0")
        }
    except Exception as e:
        print(f"[ERROR] Failed to fetch channel info: {e}")
        return None


def clean_title_and_tags(raw_title: str):
    """
    Cleans raw title, removes noisy hashtags/typos (e.g. bbbgshow),
    and formats clean, high-CTR YouTube Shorts title under 100 characters.
    """
    # Remove existing hashtags from title text
    title_text = re.sub(r'#\S+', '', raw_title).strip()
    # Normalize multiple spaces and punctuation
    title_text = re.sub(r'\s+', ' ', title_text)
    title_text = title_text.strip(". ")

    # Add primary hashtags for YouTube Shorts discovery
    suffix = " #Shorts #TheBigBangTheory"
    max_len = 100 - len(suffix)
    if len(title_text) > max_len:
        title_text = title_text[:max_len - 3] + "..."

    final_title = f"{title_text}{suffix}"

    tags = [
        "shorts",
        "the big bang theory",
        "tbbt",
        "sheldon cooper",
        "sheldon",
        "amy farrah fowler",
        "penny",
        "leonard",
        "sitcom",
        "comedy",
        "funny shorts",
        "viral shorts",
        "best sitcom moments"
    ]

    description = (
        f"{title_text}\n\n"
        f"Classic moment from The Big Bang Theory! Don't forget to like and subscribe for daily comedy shorts.\n\n"
        f"#Shorts #TheBigBangTheory #SheldonCooper #Sitcom #Comedy #Funny"
    )

    return final_title, description, tags


def init_or_load_queue(start_date_str=None, publish_hour: int = 18):
    """
    Initializes or updates the upload queue from manifest.json.
    Assigns sequential dates (one daily) starting from start_date_str (YYYY-MM-DD).
    """
    if not MANIFEST_FILE.exists():
        print(f"[ERROR] Manifest file not found: {MANIFEST_FILE}")
        sys.exit(1)

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    existing_queue = {}
    if QUEUE_FILE.exists():
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for item in saved.get("queue", []):
                    existing_queue[item["id"]] = item
        except Exception:
            pass

    today = date.today()
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    else:
        # Default to tomorrow
        start_date = today + timedelta(days=1)

    queue = []
    current_date = start_date

    shorts = manifest.get("shorts", [])
    for idx, s in enumerate(shorts, start=1):
        vid_id = s["id"]
        local_path = s["local_path"]

        # Check if already in existing queue
        if vid_id in existing_queue and existing_queue[vid_id].get("status") == "uploaded":
            item = existing_queue[vid_id]
        else:
            final_title, description, tags = clean_title_and_tags(s.get("title", f"Short #{idx}"))
            scheduled_date_str = current_date.strftime("%Y-%m-%d")
            # Publish time ISO (e.g. 18:00 UTC)
            scheduled_iso = f"{scheduled_date_str}T{publish_hour:02d}:00:00Z"

            item = {
                "queue_index": idx,
                "id": vid_id,
                "local_path": local_path,
                "file_name": os.path.basename(local_path),
                "title": final_title,
                "description": description,
                "tags": tags,
                "scheduled_date": scheduled_date_str,
                "publish_at_utc": scheduled_iso,
                "status": "pending",
                "youtube_id": None,
                "youtube_url": None,
                "uploaded_at": None
            }
            current_date += timedelta(days=1)

        queue.append(item)

    queue_data = {
        "channel_source": manifest.get("channel_url", "https://www.youtube.com/@diepvo8265"),
        "total_items": len(queue),
        "publish_hour_utc": publish_hour,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "queue": queue
    }

    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue_data, f, indent=2, ensure_ascii=False)

    print(f"[QUEUE] Upload queue initialized with {len(queue)} items at: {QUEUE_FILE}")
    return queue_data


def print_status():
    """Prints current upload queue progress and upcoming schedule."""
    if not QUEUE_FILE.exists():
        init_or_load_queue()

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    queue = data.get("queue", [])
    uploaded = [q for q in queue if q.get("status") == "uploaded"]
    pending = [q for q in queue if q.get("status") == "pending"]

    print("\n" + "=" * 80)
    print("                YOUTUBE SHORTS DAILY UPLOAD QUEUE STATUS")
    print("=" * 80)
    print(f"Total Shorts in Queue: {len(queue)}")
    print(f"Already Uploaded:      {len(uploaded)}")
    print(f"Pending Daily Uploads: {len(pending)}")
    print(f"Daily Schedule:        1 short/day at {data.get('publish_hour_utc', 18)}:00 UTC")

    if uploaded:
        print("\n--- Recent Uploads ---")
        for u in uploaded[-5:]:
            print(f"  [Slot {u['queue_index']:02d}] {u['title'][:50]} -> {u.get('youtube_url')}")

    if pending:
        print("\n--- Next 7 Pending in Schedule ---")
        for p in pending[:7]:
            print(f"  [Slot {p['queue_index']:02d}] Date: {p['scheduled_date']} | {p['title'][:60]}")
    else:
        print("\nAll shorts in the queue have been uploaded!")
    print("=" * 80 + "\n")


def upload_next_short(schedule_release=False, slot_index=None):
    """
    Uploads the next pending short from the queue (or a specific slot).
    If schedule_release is True, sets publishAt to the scheduled datetime (video remains private until then).
    If False, publishes immediately as public.
    """
    if not QUEUE_FILE.exists():
        init_or_load_queue()

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    queue = data.get("queue", [])
    target_item = None

    if slot_index is not None:
        for q in queue:
            if q["queue_index"] == slot_index:
                target_item = q
                break
        if not target_item:
            print(f"[ERROR] Slot index {slot_index} not found in queue.")
            return False
    else:
        for q in queue:
            if q.get("status") == "pending":
                target_item = q
                break

    if not target_item:
        print("[QUEUE] No pending shorts left to upload! All 55 are uploaded.")
        return False

    local_path = Path(target_item["local_path"])
    if not local_path.exists():
        print(f"[ERROR] Local video file does not exist: {local_path}")
        return False

    print("\n" + "=" * 80)
    print(f"Uploading Slot #{target_item['queue_index']}: {target_item['title']}")
    print(f"File: {local_path.name} ({local_path.stat().st_size / (1024*1024):.2f} MB)")
    print(f"Scheduled Date: {target_item['scheduled_date']}")
    print("=" * 80)

    youtube = get_authenticated_service()

    # Determine status & privacy
    status = {"selfDeclaredMadeForKids": False}
    if schedule_release:
        status["privacyStatus"] = "private"
        status["publishAt"] = target_item["publish_at_utc"]
        print(f"[STATUS] Uploading as PRIVATE, scheduled to publish at: {target_item['publish_at_utc']}")
    else:
        status["privacyStatus"] = "public"
        print(f"[STATUS] Publishing immediately as PUBLIC")

    body = {
        "snippet": {
            "title": target_item["title"],
            "description": target_item["description"],
            "tags": target_item["tags"],
            "categoryId": "23",  # Comedy (or 24 Entertainment)
        },
        "status": status,
    }

    try:
        media = MediaFileUpload(str(local_path), chunksize=256 * 1024 * 10, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        print("[UPLOAD] Upload in progress...")
        while response is None:
            status_progress, response = request.next_chunk()
            if status_progress:
                pct = int(status_progress.progress() * 100)
                print(f"  --> Uploaded {pct}%")

        video_id = response["id"]
        youtube_url = f"https://youtube.com/shorts/{video_id}"
        print(f"\n[SUCCESS] Upload Complete!")
        print(f"Video ID: {video_id}")
        print(f"Short URL: {youtube_url}")

        # Update queue
        target_item["status"] = "uploaded"
        target_item["youtube_id"] = video_id
        target_item["youtube_url"] = youtube_url
        target_item["uploaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return True

    except HttpError as e:
        print(f"[HTTP ERROR] Upload failed: {e}")
        target_item["status"] = "failed"
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error during upload: {e}")
        return False


def setup_windows_task(run_time: str = "18:00"):
    """
    Sets up a Windows Task Scheduler task that runs the daily upload script
    automatically every day at run_time (e.g. 18:00).
    """
    task_name = "DailyYouTubeShortsUpload"
    python_exe = sys.executable
    script_path = str(Path(__file__).resolve())
    action_cmd = f'"{python_exe}" "{script_path}" --upload-next'

    print(f"\n[SCHEDULER] Configuring Windows Scheduled Task '{task_name}'...")
    print(f"Execution: Daily at {run_time}")
    print(f"Command: {action_cmd}")

    # Use schtasks to create/update daily task
    schtasks_cmd = f'schtasks /Create /SC DAILY /TN "{task_name}" /TR "{action_cmd}" /ST {run_time} /F'
    ret = os.system(schtasks_cmd)
    if ret == 0:
        print(f"[SCHEDULER SUCCESS] Task '{task_name}' created successfully in Windows Task Scheduler.")
        print(f"Windows will automatically execute this script every day at {run_time}!")
    else:
        print(f"[SCHEDULER WARNING] schtasks returned code {ret}. You can also run the task manually or via cron.")


def main():
    parser = argparse.ArgumentParser(description="Daily YouTube Shorts Uploader & Queue Scheduler")
    parser.add_argument("--init-queue", action="store_true", help="Initialize or reset upload queue from manifest.json")
    parser.add_argument("--start-date", type=str, default=None, help="Start date for queue (YYYY-MM-DD)")
    parser.add_argument("--publish-hour", type=int, default=18, help="Publish hour UTC (0-23, default 18)")
    parser.add_argument("--auth", action="store_true", help="Authenticate with YouTube and display channel info")
    parser.add_argument("--status", action="store_true", help="Display current upload queue status and upcoming schedule")
    parser.add_argument("--upload-next", action="store_true", help="Upload the next pending short in the queue")
    parser.add_argument("--upload-count", type=int, default=1, help="Number of shorts to upload (default: 1)")
    parser.add_argument("--slot", type=int, default=None, help="Upload a specific slot index from the queue")
    parser.add_argument("--schedule", action="store_true", help="Upload as private scheduled release (publishAt)")
    parser.add_argument("--setup-scheduler", type=str, default=None, help="Configure Windows Task Scheduler daily at specified time (HH:MM)")

    args = parser.parse_args()

    if args.init_queue:
        init_or_load_queue(args.start_date, args.publish_hour)
        print_status()
    elif args.auth:
        print("\n--- Verifying YouTube Authentication ---")
        youtube = get_authenticated_service()
        info = get_channel_info(youtube)
        if info:
            print("\n" + "=" * 60)
            print(f"Channel Name:     {info['title']}")
            print(f"Channel Handle:   {info['handle']}")
            print(f"Channel ID:       {info['id']}")
            print(f"Subscribers:      {info['subscribers']}")
            print(f"Total Videos:     {info['videos']}")
            print("=" * 60)
            print("OAuth authentication verified successfully!\n")
        else:
            print("[WARNING] Could not retrieve channel info. Check permissions.")
    elif args.status:
        print_status()
    elif args.upload_next or args.upload_count > 1:
        count = args.upload_count if args.upload_count > 1 else 1
        for i in range(count):
            print(f"\n>>> Processing upload {i+1} of {count}...")
            ok = upload_next_short(schedule_release=args.schedule, slot_index=args.slot)
            if not ok:
                break
    elif args.setup_scheduler:
        setup_windows_task(args.setup_scheduler)
    else:
        # Default behavior: show status
        print_status()


if __name__ == "__main__":
    main()
