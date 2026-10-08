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
import re
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
        "local_token": CONFIG_DIR / "token_just_nature.json",
        "local_media_dirs": [Path(r"D:\Media\shorts\just_nature"), Path(r"D:\Media\shorts\just_nature\norway")]
    },
    "asset_vault": {
        "name": "The Asset Vault",
        "handle": "@theassetvault000",
        "category_id": "27", # Education / Finance
        "queue_file": DATA_DIR / "wealth_shorts" / "wealth_shorts_queue.json",
        "token_env": "YOUTUBE_TOKEN_ASSET_VAULT",
        "local_token": CONFIG_DIR / "token.json",
        "local_media_dirs": [Path(r"D:\Media\shorts\the_asset_vault")]
    },
    "sitcom_vault": {
        "name": "Sitcom Vault Daily",
        "handle": "@sitcomvaultdaily",
        "category_id": "24", # Entertainment / Comedy
        "queue_file": DATA_DIR / "instagram_queue.json",
        "token_env": "YOUTUBE_TOKEN_SITCOM_VAULT",
        "local_token": CONFIG_DIR / "token_sitcom.json",
        "mega_folder": "https://mega.nz/folder/egwTiY4L#4K5dT03RmF_5KkU8mgFU-g",
        "local_media_dirs": [Path(r"D:\Media\shorts\optimized"), Path(r"D:\Media\shorts\diepvo8265_reels"), Path(r"D:\Media\shorts\himym")]
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

def download_from_mega(mega_folder, filename, download_dir, item=None, cfg=None):
    download_dir = Path(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    # Clean filename by stripping any path prefixes (e.g. Windows backslashes on Linux runners)
    clean_name = None
    if filename:
        clean_name = Path(str(filename).replace("\\", "/")).name

    if item and item.get("local_path"):
        lp = Path(item["local_path"])
        if lp.exists() and lp.stat().st_size > 0:
            log(f"Using direct local file: {lp}")
            return lp

    # Check if file exists locally in channel's specific media dirs first (for local runs on Windows)
    local_dirs = (cfg.get("local_media_dirs") if cfg else None) or [
        Path(r"D:\Media\shorts\just_nature"),
        Path(r"D:\Media\shorts\just_nature\norway"),
        Path(r"D:\Media\shorts\the_asset_vault")
    ]
    for fallback_dir in local_dirs:
        if fallback_dir.exists():
            if clean_name:
                p = fallback_dir / clean_name
                if p.exists() and p.stat().st_size > 0:
                    log(f"Using local PC file: {p}")
                    return p
            if item:
                vid_id = item.get("id", "").replace("asset_vault_", "")
                idx = item.get("index")
                for f in fallback_dir.glob("*.mp4"):
                    if vid_id and vid_id in f.name:
                        log(f"Using local PC file (id match): {f}")
                        return f
                    if idx and (f"_{idx:02d}_" in f.name or f"_{idx}_" in f.name):
                        log(f"Using local PC file (index match): {f}")
                        return f

    if clean_name:
        target_path = download_dir / clean_name
        if target_path.exists() and target_path.stat().st_size > 0:
            log(f"File already downloaded: {target_path} ({target_path.stat().st_size / (1024*1024):.2f} MB)")
            return target_path

    display_name = clean_name or (item.get("title") if item else "unknown")
    log(f"Downloading '{display_name}' from MEGA folder {mega_folder}...")

    # Try downloading via mega-get in Linux / GitHub Actions
    try:
        cmd = ["mega-get", mega_folder, str(download_dir)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.stdout:
            log(f"[mega-get stdout] {proc.stdout.strip()[:300]}")
        if proc.stderr:
            log(f"[mega-get stderr] {proc.stderr.strip()[:300]}")
    except FileNotFoundError:
        log("[WARNING] mega-get not found on this system. Assuming local file or manual download.")

    # 1. Exact filename match
    if clean_name:
        matched = [p for p in download_dir.rglob("*") if p.is_file() and p.name == clean_name and p.stat().st_size > 0]
        if matched:
            log(f"Successfully retrieved from MEGA (exact match): {matched[0]}")
            return matched[0]

    # 2. Fuzzy match by video ID or index in downloaded files (handles emoji discrepancies between Windows/Linux)
    if item:
        vid_id = item.get("id", "").replace("asset_vault_", "")
        idx = item.get("index")
        for f in download_dir.rglob("*.mp4"):
            if f.is_file() and f.stat().st_size > 0:
                if vid_id and vid_id in f.name:
                    log(f"Successfully retrieved from MEGA (matched by ID {vid_id}): {f}")
                    return f
                if idx and (f"_{idx:02d}_" in f.name or f"_{idx}_" in f.name):
                    log(f"Successfully retrieved from MEGA (matched by index {idx}): {f}")
                    return f

    raise FileNotFoundError(f"Could not download or find video for item: {display_name}")

def clean_youtube_metadata(item, cfg):
    """
    Cleans and optimizes titles, descriptions, and tags for YouTube Shorts.
    - Removes [Part 1] / [Part 2] prefixes to prevent swipe-aways
    - Ensures #Shorts is present in the title
    - Purges Instagram hashtags (#reels, #explorepage) and jargon ('double-tap')
    - Adds YouTube-native channel CTAs and targeted SEO tags
    """
    raw_title = item.get("youtube_title") or item.get("title", "")
    
    # Strip [Part X], (Part X), Part X:, etc.
    cleaned_title = re.sub(r'^\s*(\[|\()?\s*part\s*\d+(\s*/\s*\d+)?\s*(\]|\))?\s*[:\-\.]?\s*', '', raw_title, flags=re.IGNORECASE)
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    
    # Ensure #Shorts is present in title
    if "#shorts" not in cleaned_title.lower():
        if len(cleaned_title) + len(" #Shorts") <= 95:
            cleaned_title = f"{cleaned_title} #Shorts"

    raw_desc = item.get("youtube_description") or item.get("description") or item.get("caption") or ""

    if cfg["name"] == "Sitcom Vault Daily":
        desc_hook = cleaned_title.replace("#Shorts", "").strip()
        clean_desc = (
            f"{desc_hook}\n\n"
            "Classic comedy gold from The Big Bang Theory! Nobody delivers punchlines like Sheldon Cooper.\n\n"
            "🔔 Subscribe to @SitcomVaultDaily for daily comedy sitcom shorts & funny TV moments!\n"
            "💬 Which sitcom scene should we feature next? Drop a comment below!\n\n"
            "#Shorts #TheBigBangTheory #TBBT #SheldonCooper #Sitcom #Comedy #FunnyMoments"
        )
        tags = [
            "Shorts", "The Big Bang Theory", "Sheldon Cooper", "Big Bang Theory Funny Moments",
            "Sitcom", "Comedy", "TBBT", "Penny and Leonard", "Shamy", "Jim Parsons",
            "Sitcom Vault Daily", "Funny TV Clips"
        ]
    elif cfg["name"] == "Just Nature":
        clean_desc = (
            f"{cleaned_title}\n\n"
            "Breathtaking scenery and peaceful nature views from around the world.\n\n"
            "🔔 Subscribe to @just.nature46 for daily relaxing 4K nature escapes!\n"
            "📍 Save this for your travel bucket list!\n\n"
            "#Shorts #Nature #RelaxingNature #4KNature #Travel #Scenery"
        )
        tags = ["Shorts", "Nature", "Relaxing Nature", "4K Nature", "Travel", "Scenery", "Earth", "Landscape"]
    elif cfg["name"] == "The Asset Vault":
        clean_desc = (
            f"{cleaned_title}\n\n"
            "Daily financial wisdom, wealth-building strategies, and success mindsets.\n\n"
            "🔔 Subscribe to @theassetvault000 for daily wealth & investing shorts!\n\n"
            "#Shorts #Finance #Wealth #Money #Investing #Business #Success"
        )
        tags = ["Shorts", "Finance", "Wealth", "Money", "Investing", "Business", "Success", "Financial Freedom"]
    else:
        clean_desc = re.sub(r'#(reels|reelsinstagram|explorepage|viralreels|comedyreels)\w*', '', raw_desc, flags=re.IGNORECASE)
        clean_desc = re.sub(r'(?i)double-tap[^\n]*', '', clean_desc).strip()
        tags = ["Shorts", "Viral", "YouTubeShorts"]

    return cleaned_title[:100], clean_desc, tags

def upload_short(youtube, video_path, item, cfg, dry_run=False):
    title, description, tags = clean_youtube_metadata(item, cfg)
    log(f"Preparing upload for YouTube:")
    log(f"  Optimized Title: {title}")
    log(f"  Tags: {tags[:5]}...")
    log(f"  File: {video_path}")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
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

def delete_scheduled_videos(youtube):
    log("Fetching all scheduled/private videos on channel...")
    ch = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_playlist_id = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    playlist_items = youtube.playlistItems().list(part="snippet,status", playlistId=uploads_playlist_id, maxResults=50).execute()
    deleted_count = 0
    for item in playlist_items.get("items", []):
        vid_id = item["snippet"]["resourceId"]["videoId"]
        title = item["snippet"]["title"]
        status_res = youtube.videos().list(part="status", id=vid_id).execute()
        if not status_res.get("items"):
            continue
        v_status = status_res["items"][0]["status"]
        privacy = v_status.get("privacyStatus")
        publish_at = v_status.get("publishAt")

        if publish_at or privacy == "private":
            log(f"Deleting scheduled video: {vid_id} | Scheduled: {publish_at} | Title: {title}")
            try:
                youtube.videos().delete(id=vid_id).execute()
                deleted_count += 1
                log(f"Deleted video {vid_id}")
            except Exception as e:
                log(f"Failed to delete {vid_id}: {e}")

    log(f"[DELETE COMPLETE] Total scheduled videos deleted: {deleted_count}")

def main():
    parser = argparse.ArgumentParser(description="YouTube Cloud Daily Publisher")
    parser.add_argument("--channel", choices=["just_nature", "asset_vault", "sitcom_vault"], default="just_nature", help="Channel key")
    parser.add_argument("--post-next", action="store_true", help="Post the next scheduled video")
    parser.add_argument("--delete-scheduled", action="store_true", help="Delete all scheduled private videos on the channel")
    parser.add_argument("--status", action="store_true", help="Show queue status")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without uploading")
    parser.add_argument("--force", action="store_true", help="Force upload regardless of future scheduled date")
    args = parser.parse_args()

    cfg = CHANNEL_CONFIGS[args.channel]

    if args.delete_scheduled:
        creds = get_credentials(cfg)
        youtube = build("youtube", "v3", credentials=creds)
        delete_scheduled_videos(youtube)
        return
    queue_file = cfg["queue_file"]

    if not queue_file.exists():
        log(f"[ERROR] Queue file does not exist: {queue_file}")
        sys.exit(1)

    with open(queue_file, "r", encoding="utf-8") as f:
        q_data = json.load(f)

    queue = q_data.get("queue", [])
    if args.channel == "sitcom_vault":
        pending = [q for q in queue if not q.get("youtube_id") and not q.get("published_at")]
    else:
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

    from datetime import timezone
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    item_date = (next_item.get("scheduled_time") or next_item.get("publish_at") or "")[:10]
    if not getattr(args, "force", False) and item_date and item_date > today_str:
        log(f"[SCHEDULE GUARD] Next item #{next_item.get('index', 1)} is scheduled for {item_date}. Current date is {today_str}. Upcoming dates are already scheduled on YouTube Studio. Skipping run.")
        return

    # Authenticate
    creds = get_credentials(cfg)
    youtube = build("youtube", "v3", credentials=creds)

    # Resolve filename and mega folder
    filename = next_item.get("filename")
    if not filename and "local_path" in next_item:
        filename = Path(next_item["local_path"]).name

    mega_folder = next_item.get("mega_folder") or q_data.get("mega_folder") or cfg.get("mega_folder")

    # Download file
    temp_dir = ROOT / "media_downloads"
    video_path = download_from_mega(mega_folder, filename, temp_dir, item=next_item, cfg=cfg)

    # Check if a high-retention trim window is defined for this clip
    trim_start = next_item.get("trim_start")
    trim_end = next_item.get("trim_end")
    if trim_start is not None and trim_end is not None:
        duration = float(trim_end) - float(trim_start)
        log(f"[TRIM] High-retention trim specified: {trim_start}s -> {trim_end}s ({duration:.1f}s total duration)")
        trimmed_name = f"{video_path.stem}_trim_{int(trim_start)}_{int(trim_end)}.mp4"
        trimmed_file = temp_dir / trimmed_name
        if not trimmed_file.exists():
            trim_cmd = [
                "ffmpeg", "-y",
                "-ss", str(trim_start),
                "-to", str(trim_end),
                "-i", str(video_path),
                "-c:v", "libx264",
                "-c:a", "aac",
                "-avoid_negative_ts", "make_zero",
                str(trimmed_file)
            ]
            res = subprocess.run(trim_cmd, capture_output=True, text=True)
            if res.returncode == 0 and trimmed_file.exists():
                log(f"[TRIM] Optimization complete! Using trimmed file: {trimmed_file}")
                video_path = trimmed_file
            else:
                log(f"[TRIM] Warning: Trim command failed, proceeding with original: {res.stderr[-150:]}")
        else:
            log(f"[TRIM] Using pre-trimmed file: {trimmed_file}")
            video_path = trimmed_file

    # Upload
    vid_id = upload_short(youtube, video_path, next_item, cfg, dry_run=args.dry_run)
    yt_url = f"https://www.youtube.com/shorts/{vid_id}"

    if not args.dry_run:
        # Update item in queue
        next_item["youtube_id"] = vid_id
        next_item["youtube_url"] = yt_url
        next_item["published_at"] = datetime.now().isoformat()

        if args.channel == "sitcom_vault":
            # For Sitcom Vault, queue status tracks Instagram posting
            if next_item.get("instagram_media_id"):
                next_item["status"] = "posted"
            # Recalculate counts based on Instagram media ID
            if "posted_items" in q_data:
                q_data["posted_items"] = sum(1 for q in queue if q.get("instagram_media_id"))
            if "pending_items" in q_data:
                q_data["pending_items"] = sum(1 for q in queue if not q.get("instagram_media_id"))
        else:
            next_item["status"] = "posted"
            if "posted_items" in q_data:
                q_data["posted_items"] = sum(1 for q in queue if q.get("status") == "posted")
            if "pending_items" in q_data:
                q_data["pending_items"] = sum(1 for q in queue if q.get("status") in ["pending", "ready_to_schedule"])

        with open(queue_file, "w", encoding="utf-8") as f:
            json.dump(q_data, f, indent=2, ensure_ascii=False)

        log(f"Updated queue file: {queue_file}")
        log(f"[ALL DONE] {cfg['name']} Reel published: {yt_url}")

        # Send Telegram notification ping
        try:
            sys.path.append(str(ROOT / "scripts"))
            from telegram_notifier import notify_published
            notify_published(
                platform="YouTube",
                channel=f"{cfg['name']} ({cfg['handle']})",
                title=next_item.get("title", ""),
                url=yt_url,
                queue_index=next_item.get("index", next_item.get("queue_index"))
            )
        except Exception as tel_err:
            log(f"[TELEGRAM] Notice: ping skipped ({tel_err})")

        # Commit and push in GitHub Actions
        commit_msg = f"chore(youtube): publish {cfg['name']} short #{next_item.get('index', 1)} ({vid_id})"
        commit_and_push_queue(queue_file, commit_msg)
    else:
        log("[DRY RUN] Complete! Queue was not modified.")

if __name__ == "__main__":
    main()
