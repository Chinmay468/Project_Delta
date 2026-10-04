"""
Unified YouTube Cloud Publisher for GitHub Actions & Local Execution.
Supports:
  --channel just_nature   (Just Nature @just.nature46)
  --channel asset_vault   (The Asset Vault @theassetvault000)
"""
import sys
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import time
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly"
]

CHANNEL_CONFIGS = {
    "just_nature": {
        "name": "Just Nature",
        "handle": "@just.nature46",
        "category_id": "19", # Travel & Events
        "queue_file": DATA_DIR / "just_nature_queue.json",
        "token_env": "YOUTUBE_TOKEN_JUST_NATURE",
        "local_token": CONFIG_DIR / "token_just_nature.json"
    },
    "asset_vault": {
        "name": "The Asset Vault",
        "handle": "@theassetvault000",
        "category_id": "27", # Education / Finance
        "queue_file": DATA_DIR / "wealth_shorts" / "wealth_shorts_queue.json",
        "token_env": "YOUTUBE_TOKEN_ASSET_VAULT",
        "local_token": CONFIG_DIR / "token.json"
    }
}

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def get_credentials(cfg):
    token_json_str = os.environ.get(cfg["token_env"])
    if token_json_str:
        log(f"Loading credentials from environment secret {cfg['token_env']}...")
        token_info = json.loads(token_json_str)
        creds = Credentials.from_authorized_user_info(token_info)
    elif cfg["local_token"].exists():
        log(f"Loading credentials from local file {cfg['local_token']}...")
        creds = Credentials.from_authorized_user_file(str(cfg["local_token"]))
    else:
        raise RuntimeError(f"No credentials found for {cfg['name']}. Set {cfg['token_env']} or provide {cfg['local_token']}")

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            log("Credentials expired. Refreshing token...")
            for attempt in range(5):
                try:
                    creds.refresh(Request())
                    log("Token refreshed successfully.")
                    if cfg["local_token"].exists() and not os.environ.get("GITHUB_ACTIONS"):
                        cfg["local_token"].write_text(creds.to_json())
                    break
                except Exception as e:
                    if attempt < 4:
                        log(f"Refresh attempt {attempt+1} failed: {e}. Retrying...")
                        time.sleep(3)
                    else:
                        raise e
        else:
            raise RuntimeError("Credentials invalid and no refresh token available.")

    return creds

def download_from_mega(mega_folder, filename, download_dir):
    download_dir = Path(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    target_path = download_dir / filename

    if target_path.exists() and target_path.stat().st_size > 0:
        log(f"File already downloaded: {target_path} ({target_path.stat().st_size / (1024*1024):.2f} MB)")
        return target_path

    # Check if file exists locally in typical PC path first
    for fallback in [
        Path(r"D:\Media\shorts\just_nature") / filename,
        Path(r"D:\Media\shorts\just_nature\norway") / filename,
        Path(r"D:\Media\shorts\the_asset_vault") / filename
    ]:
        if fallback.exists():
            log(f"Using local PC file: {fallback}")
            return fallback

    log(f"Downloading '{filename}' from MEGA folder {mega_folder}...")
    
    # Try downloading via mega-get in Linux / GitHub Actions
    try:
        cmd = ["mega-get", mega_folder, str(download_dir)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        log("[WARNING] mega-get not found on this system. Assuming local file or manual download.")
    
    # Search for the file in download_dir (recursively in case MEGA creates a subfolder)
    matched = list(download_dir.rglob(filename))
    if matched and matched[0].exists() and matched[0].stat().st_size > 0:
        log(f"Successfully retrieved from MEGA: {matched[0]}")
        return matched[0]

    raise FileNotFoundError(f"Could not download or find '{filename}'.")

def upload_short(youtube, video_path, item, cfg, dry_run=False):
    log(f"Preparing upload for: {item['title']}")
    log(f"File: {video_path}")

    body = {
        "snippet": {
            "title": item["title"][:100],
            "description": item["description"],
            "tags": item.get("tags", []),
            "categoryId": cfg["category_id"],
            "defaultLanguage": "en"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    if dry_run:
        log("[DRY RUN] Verification successful. Skipping actual upload call.")
        return "dry_run_id_12345"

    media = MediaFileUpload(str(video_path), chunksize=1024*1024*4, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            log(f"  Uploading: {int(status.progress() * 100)}%")

    vid_id = response["id"]
    log(f"[SUCCESS] Uploaded to YouTube! Video ID: {vid_id}")
    return vid_id

def commit_and_push_queue(queue_file, commit_msg):
    if os.environ.get("GITHUB_ACTIONS") != "true":
        log("Not running in GitHub Actions. Skipping git push.")
        return

    log("Running in GitHub Actions. Committing and pushing updated queue...")
    subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "add", str(queue_file)], check=True)
    subprocess.run(["git", "commit", "-m", commit_msg], check=True)
    subprocess.run(["git", "push", "origin", "main"], check=True)
    log("Queue state pushed to GitHub successfully.")

def main():
    parser = argparse.ArgumentParser(description="YouTube Cloud Daily Publisher")
    parser.add_argument("--channel", choices=["just_nature", "asset_vault"], default="just_nature", help="Channel key")
    parser.add_argument("--post-next", action="store_true", help="Post the next scheduled video")
    parser.add_argument("--status", action="store_true", help="Show queue status")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without uploading")
    args = parser.parse_args()

    cfg = CHANNEL_CONFIGS[args.channel]
    queue_file = cfg["queue_file"]

    if not queue_file.exists():
        log(f"[ERROR] Queue file does not exist: {queue_file}")
        sys.exit(1)

    with open(queue_file, "r", encoding="utf-8") as f:
        q_data = json.load(f)

    queue = q_data.get("queue", [])
    pending = [q for q in queue if q.get("status") in ["pending", "ready_to_schedule"]]

    if args.status or (not args.post_next and not args.dry_run):
        print(f"\n{'='*60}")
        print(f" CHANNEL: {cfg['name']} ({cfg['handle']})")
        print(f"{'='*60}")
        print(f"Total items in queue:   {len(queue)}")
        print(f"Posted/Scheduled items: {len(queue) - len(pending)}")
        print(f"Pending items:          {len(pending)}")
        if pending:
            nxt = pending[0]
            print(f"\nNext up (#{nxt.get('index', 1)}):")
            print(f"  Title:     {nxt.get('title')}")
            print(f"  File:      {nxt.get('filename') or nxt.get('video_path')}")
            print(f"  Scheduled: {nxt.get('scheduled_time') or nxt.get('publish_at')}")
        print(f"{'='*60}\n")
        return

    if not pending:
        log(f"No pending videos to publish for {cfg['name']}! All {len(queue)} items are already posted.")
        return

    next_item = pending[0]
    log(f"Selected next item: #{next_item.get('index', 1)}: {next_item['title']}")

    # Authenticate
    creds = get_credentials(cfg)
    youtube = build("youtube", "v3", credentials=creds)

    # Resolve filename and mega folder
    filename = next_item.get("filename")
    if not filename and "local_path" in next_item:
        filename = Path(next_item["local_path"]).name

    mega_folder = next_item.get("mega_folder") or q_data.get("mega_folder")

    # Download file
    temp_dir = ROOT / "media_downloads"
    video_path = download_from_mega(mega_folder, filename, temp_dir)

    # Upload
    vid_id = upload_short(youtube, video_path, next_item, cfg, dry_run=args.dry_run)
    yt_url = f"https://www.youtube.com/shorts/{vid_id}"

    if not args.dry_run:
        # Update item in queue
        next_item["status"] = "posted"
        next_item["youtube_id"] = vid_id
        next_item["youtube_url"] = yt_url
        next_item["published_at"] = datetime.now().isoformat()

        # Recalculate counts
        if "posted_items" in q_data:
            q_data["posted_items"] = sum(1 for q in queue if q.get("status") == "posted")
        if "pending_items" in q_data:
            q_data["pending_items"] = sum(1 for q in queue if q.get("status") in ["pending", "ready_to_schedule"])

        with open(queue_file, "w", encoding="utf-8") as f:
            json.dump(q_data, f, indent=2, ensure_ascii=False)

        log(f"Updated queue file: {queue_file}")
        log(f"[ALL DONE] {cfg['name']} Reel published: {yt_url}")

        # Commit and push in GitHub Actions
        commit_msg = f"chore(youtube): publish {cfg['name']} short #{next_item.get('index', 1)} ({vid_id})"
        commit_and_push_queue(queue_file, commit_msg)
    else:
        log("[DRY RUN] Complete! Queue was not modified.")

if __name__ == "__main__":
    main()
