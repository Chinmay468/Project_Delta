"""
Official Meta Instagram Graph API Reels Publisher
==================================================
Publishes vertical Reels directly to Instagram using Meta's official Graph API.
Zero browser emulation, zero cookie expiration, 100% permanent cloud-native posting.

Features:
- Official Resumable Binary Upload protocol (streams video directly from disk or MEGA).
- Discovers Instagram Business ID dynamically from Facebook Page or direct ID.
- Seamless integration with data/instagram_queue.json.
- Full Telegram notification ping and failure alerting.
- Automatic Git commit & push when running inside GitHub Actions.
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Force UTF-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import dotenv_values
except ImportError:
    def dotenv_values(path):
        return {}

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"
ENV_FILE = CONFIG_DIR / ".env"
QUEUE_FILE = DATA_DIR / "instagram_queue.json"

DEFAULT_PAGE_ID = "1304317289439428"  # Sitcom Vault Facebook Page
GRAPH_API_VERSION = "v20.0"


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def get_meta_config():
    """Retrieves access token, page ID, and IG account ID from env or .env file."""
    env_vars = {}
    if ENV_FILE.exists():
        try:
            env_vars = dotenv_values(str(ENV_FILE))
        except Exception:
            pass

    token = (
        os.environ.get("INSTAGRAM_ACCESS_TOKEN")
        or os.environ.get("META_ACCESS_TOKEN")
        or os.environ.get("FB_PAGE_ACCESS_TOKEN")
        or env_vars.get("INSTAGRAM_ACCESS_TOKEN")
        or env_vars.get("META_ACCESS_TOKEN")
        or env_vars.get("FB_PAGE_ACCESS_TOKEN")
        or ""
    ).strip()

    page_id = (
        os.environ.get("FB_PAGE_ID")
        or env_vars.get("FB_PAGE_ID")
        or DEFAULT_PAGE_ID
    ).strip()

    ig_user_id = (
        os.environ.get("INSTAGRAM_ACCOUNT_ID")
        or env_vars.get("INSTAGRAM_ACCOUNT_ID")
        or ""
    ).strip()

    return token, page_id, ig_user_id


def resolve_instagram_user_id(token: str, page_id: str, ig_user_id: str = "") -> str:
    """Discovers the connected Instagram Business / Creator account ID from the Facebook Page."""
    if ig_user_id:
        return ig_user_id

    if not token:
        raise ValueError("Missing INSTAGRAM_ACCESS_TOKEN / META_ACCESS_TOKEN! Please configure your Meta Access Token.")

    log(f"Resolving connected Instagram Business Account for Facebook Page ID {page_id}...")
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}"
    params = {
        "fields": "name,instagram_business_account,connected_instagram_account",
        "access_token": token
    }

    resp = requests.get(url, params=params, timeout=20)
    data = resp.json()

    if resp.status_code != 200 or "error" in data:
        err_msg = data.get("error", {}).get("message", "Unknown Meta Graph API error")
        raise RuntimeError(f"Failed to query Facebook Page ({resp.status_code}): {err_msg}")

    ig_acc = data.get("instagram_business_account") or data.get("connected_instagram_account")
    if not ig_acc or "id" not in ig_acc:
        raise RuntimeError(
            f"No Instagram Business Account linked to Facebook Page '{data.get('name', page_id)}'.\n"
            "Please link @sitcomvaultdaily to the Facebook Page in Meta Business Suite."
        )

    resolved_id = str(ig_acc["id"])
    log(f"Found linked Instagram Business Account ID: {resolved_id} (Page: {data.get('name')})")
    return resolved_id


def download_from_mega(mega_folder: str, filename: str, download_dir: Path, item: dict = None) -> Path:
    """Downloads or retrieves the video file on disk."""
    download_dir = Path(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    clean_name = None
    if filename:
        clean_name = Path(str(filename).replace("\\", "/")).name

    # Check local path on Windows
    if item and item.get("local_path"):
        lp = Path(item["local_path"])
        if lp.exists() and lp.stat().st_size > 0:
            log(f"Using direct local file: {lp}")
            return lp

    local_dirs = [
        Path(r"D:\Media\shorts\diepvo8265_reels"),
        Path(r"D:\Media\shorts\optimized"),
        Path(r"D:\Media\shorts")
    ]
    for d in local_dirs:
        if d.exists() and clean_name:
            p = d / clean_name
            if p.exists() and p.stat().st_size > 0:
                log(f"Using local PC file: {p}")
                return p

    if clean_name:
        target_path = download_dir / clean_name
        if target_path.exists() and target_path.stat().st_size > 0:
            return target_path

    # Try downloading from MEGA in GitHub Actions
    if mega_folder:
        log(f"Downloading from MEGA folder {mega_folder}...")
        try:
            cmd = ["mega-get", mega_folder, str(download_dir)]
            subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except Exception as e:
            log(f"[WARNING] mega-get notice: {e}")

    # Exact filename match
    if clean_name:
        matched = [p for p in download_dir.rglob("*") if p.is_file() and p.name == clean_name and p.stat().st_size > 0]
        if matched:
            return matched[0]

    # File name fallback
    if item and item.get("file_name"):
        fname = Path(str(item["file_name"]).replace("\\", "/")).name
        matched = [p for p in download_dir.rglob("*") if p.is_file() and p.name == fname and p.stat().st_size > 0]
        if matched:
            return matched[0]

    # Prefix match (e.g. diepvo8265_04_part2)
    if clean_name and "_" in clean_name:
        parts = clean_name.split("_")
        if len(parts) >= 3:
            prefix = "_".join(parts[:3])
            matched = [p for p in download_dir.rglob("*.mp4") if p.is_file() and p.name.startswith(prefix) and p.stat().st_size > 0]
            if matched:
                return matched[0]

    raise FileNotFoundError(f"Could not find video file for item: {clean_name or filename}")


def publish_reel_via_graph_api(ig_user_id: str, token: str, video_path: Path, caption: str, dry_run: bool = False) -> dict:
    """
    Publishes a vertical Reel to Instagram via Meta's Official Resumable Graph API.
    Flow:
    1. POST /media (upload_type=resumable, media_type=REELS) -> gets container_id & upload_uri
    2. POST {upload_uri} (streams video binary)
    3. GET /{container_id} (polls status until FINISHED)
    4. POST /media_publish (publishes creation_id) -> gets live Instagram media_id
    """
    file_size = video_path.stat().st_size
    log(f"Publishing Reel to Instagram (@{ig_user_id}):")
    log(f"  File: {video_path.name} ({file_size / (1024*1024):.2f} MB)")
    log(f"  Caption: {caption[:60]}...")

    if dry_run:
        log("[DRY RUN] Verification mode: Validating Meta Graph API credentials and container access...")
        test_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}"
        test_resp = requests.get(test_url, params={"fields": "username,name", "access_token": token}, timeout=15)
        test_data = test_resp.json()
        if test_resp.status_code != 200 or "error" in test_data:
            err = test_data.get("error", {}).get("message", "API test error")
            raise RuntimeError(f"Graph API Validation Failed: {err}")
        log(f"[DRY RUN SUCCESS] Verified Instagram account @{test_data.get('username', ig_user_id)}! Ready to post.")
        return {"media_id": "DRY_RUN_ID", "url": "https://www.instagram.com/reel/dry_run", "status": "simulated"}

    # PHASE 1: Initialize Resumable Container Session
    log("[GRAPH API] Phase 1: Requesting upload session from Meta Reels API...")
    init_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media"
    init_payload = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "share_to_feed": "true",
        "access_token": token
    }

    init_resp = requests.post(init_url, data=init_payload, timeout=30)
    init_data = init_resp.json()

    if init_resp.status_code != 200 or "id" not in init_data:
        err = init_data.get("error", {}).get("message", init_resp.text)
        raise RuntimeError(f"Container initialization failed ({init_resp.status_code}): {err}")

    container_id = init_data["id"]
    upload_uri = init_data.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{GRAPH_API_VERSION}/{container_id}"
    log(f"[GRAPH API] Container created! Container ID: {container_id}")

    # PHASE 2: Upload Video Binary Bytes
    log(f"[GRAPH API] Phase 2: Uploading {file_size / (1024*1024):.2f} MB binary payload to {upload_uri}...")
    upload_headers = {
        "Authorization": f"OAuth {token}",
        "offset": "0",
        "file_size": str(file_size),
        "Content-Type": "application/octet-stream",
        "Content-Length": str(file_size)
    }

    with open(video_path, "rb") as vf:
        video_bytes = vf.read()

    upload_resp = requests.post(upload_uri, headers=upload_headers, data=video_bytes, timeout=300)
    if upload_resp.status_code not in (200, 201):
        raise RuntimeError(f"Binary transfer failed ({upload_resp.status_code}): {upload_resp.text}")

    log("[GRAPH API] Binary upload accepted by Meta servers! Transcoding in progress...")

    # PHASE 3: Poll Container Status until FINISHED
    log("[GRAPH API] Phase 3: Waiting for Meta server-side video processing...")
    status_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{container_id}"
    max_wait = 180  # 3 minutes
    start_time = time.time()
    ready = False

    while time.time() - start_time < max_wait:
        time.sleep(6)
        st_resp = requests.get(status_url, params={"fields": "status_code,status", "access_token": token}, timeout=15)
        st_data = st_resp.json()
        code = st_data.get("status_code", "").upper()

        if code == "FINISHED":
            log("[GRAPH API] Video processing complete! Ready for live publication.")
            ready = True
            break
        elif code in ("ERROR", "EXPIRED"):
            err_detail = st_data.get("status", "Video processing failed")
            raise RuntimeError(f"Meta video processing failed with status: {code} ({err_detail})")
        else:
            elapsed = int(time.time() - start_time)
            log(f"  [Processing] Status: {code or 'IN_PROGRESS'} ({elapsed}s elapsed)...")

    if not ready:
        raise TimeoutError("Meta video processing timed out after 3 minutes.")

    # PHASE 4: Publish Container Live to Instagram Feed
    log("[GRAPH API] Phase 4: Publishing Reel live to Instagram...")
    pub_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}/media_publish"
    pub_payload = {
        "creation_id": container_id,
        "access_token": token
    }

    pub_resp = requests.post(pub_url, data=pub_payload, timeout=30)
    pub_data = pub_resp.json()

    if pub_resp.status_code != 200 or "id" not in pub_data:
        err = pub_data.get("error", {}).get("message", pub_resp.text)
        raise RuntimeError(f"Publishing request failed ({pub_resp.status_code}): {err}")

    media_id = pub_data["id"]

    # PHASE 5: Retrieve Live Permalink
    time.sleep(2)
    media_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}"
    m_resp = requests.get(media_url, params={"fields": "id,permalink,shortcode", "access_token": token}, timeout=15)
    m_data = m_resp.json()

    ig_permalink = m_data.get("permalink") or f"https://www.instagram.com/reel/{m_data.get('shortcode', media_id)}/"
    log(f"🎉 [ALL DONE] Instagram Reel Published Live: {ig_permalink}")

    return {
        "media_id": media_id,
        "url": ig_permalink,
        "shortcode": m_data.get("shortcode", ""),
        "status": "published"
    }


def commit_and_push_queue(queue_file: Path, commit_msg: str):
    """Commits and pushes queue update in GitHub Actions."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    try:
        log("Running in GitHub Actions. Committing and pushing updated queue...")
        subprocess.run(["git", "config", "--local", "user.email", "action@github.com"], check=True)
        subprocess.run(["git", "config", "--local", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "add", str(queue_file)], check=True)
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)

        for attempt in range(3):
            res = subprocess.run(["git", "push"], capture_output=True, text=True)
            if res.returncode == 0:
                log("Queue state pushed to GitHub successfully.")
                return
            subprocess.run(["git", "pull", "--rebase"], capture_output=True)
            time.sleep(2)
    except Exception as e:
        log(f"[GIT ERROR] Failed to commit and push queue: {e}")


def main():
    parser = argparse.ArgumentParser(description="Official Meta Instagram Graph API Reels Publisher")
    parser.add_argument("--post-next", action="store_true", help="Post the next scheduled video in the queue")
    parser.add_argument("--post-index", type=int, help="Post a specific queue_index")
    parser.add_argument("--status", action="store_true", help="Show queue and Instagram account status")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without publishing live")
    args = parser.parse_args()

    token, page_id, ig_user_id = get_meta_config()

    if not QUEUE_FILE.exists():
        log(f"[ERROR] Queue file does not exist: {QUEUE_FILE}")
        sys.exit(1)

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        q_data = json.load(f)

    queue = q_data.get("queue", [])

    if args.status or (not args.post_next and args.post_index is None and not args.dry_run):
        print("\n" + "=" * 60)
        print("   META INSTAGRAM GRAPH API PIPELINE STATUS")
        print("=" * 60)
        print(f"Facebook Page ID:     {page_id}")
        print(f"Access Token:         {'[CONFIGURED]' if token else '[MISSING]'}")

        if token:
            try:
                resolved_id = resolve_instagram_user_id(token, page_id, ig_user_id)
                test_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{resolved_id}"
                test_resp = requests.get(test_url, params={"fields": "username,name", "access_token": token}, timeout=15)
                acc = test_resp.json()
                print(f"Instagram Account:    @{acc.get('username')} (ID: {resolved_id})")
                print(f"Connection Status:    ACTIVE & VERIFIED ✅")
            except Exception as e:
                print(f"Connection Status:    ERROR ❌ ({e})")

        posted = [q for q in queue if q.get("status") == "posted" or q.get("instagram_media_id")]
        pending = [q for q in queue if q.get("status") != "posted" and not q.get("instagram_media_id")]
        print(f"\nTotal queue items:    {len(queue)}")
        print(f"Posted items:         {len(posted)}")
        print(f"Pending items:        {len(pending)}")
        if pending:
            nxt = pending[0]
            print(f"\nNext up (#{nxt.get('queue_index', 1)}):")
            print(f"  Title:     {nxt.get('title')}")
            print(f"  File:      {nxt.get('file_name') or nxt.get('local_path')}")
        print("=" * 60 + "\n")
        return

    # Select item to post
    if args.post_index:
        matched = [q for q in queue if q.get("queue_index") == args.post_index]
        if not matched:
            log(f"[ERROR] No queue item found with queue_index {args.post_index}")
            sys.exit(1)
        target_item = matched[0]
    else:
        pending = [q for q in queue if q.get("status") != "posted" and not q.get("instagram_media_id")]
        if not pending:
            log("All items in queue are already posted!")
            return
        target_item = pending[0]

    log(f"Selected item #{target_item.get('queue_index', 1)}: {target_item.get('title')}")

    try:
        # Resolve target Instagram Business ID
        resolved_ig_id = resolve_instagram_user_id(token, page_id, ig_user_id)

        # Locate or download video
        temp_dir = REPO_ROOT / "media_downloads"
        filename = target_item.get("file_name") or target_item.get("filename")
        if not filename and "local_path" in target_item:
            filename = Path(target_item["local_path"]).name
        mega_folder = target_item.get("mega_folder") or q_data.get("mega_folder")

        video_path = download_from_mega(mega_folder, filename, temp_dir, item=target_item)

        # Build clean caption
        caption = target_item.get("caption") or target_item.get("title", "")

        # Publish Reel
        pub_result = publish_reel_via_graph_api(
            ig_user_id=resolved_ig_id,
            token=token,
            video_path=video_path,
            caption=caption,
            dry_run=args.dry_run
        )

        if not args.dry_run:
            # Update queue item
            target_item["status"] = "posted"
            target_item["instagram_media_id"] = pub_result["media_id"]
            target_item["instagram_url"] = pub_result["url"]
            target_item["instagram_code"] = pub_result.get("shortcode", "")
            target_item["posted_at"] = datetime.now().isoformat()

            if "posted_items" in q_data:
                q_data["posted_items"] = sum(1 for q in queue if q.get("status") == "posted" or q.get("instagram_media_id"))
            if "pending_items" in q_data:
                q_data["pending_items"] = sum(1 for q in queue if q.get("status") != "posted" and not q.get("instagram_media_id"))

            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(q_data, f, indent=2, ensure_ascii=False)

            log(f"Updated queue file: {QUEUE_FILE}")

            # Send Telegram notification
            try:
                sys.path.append(str(REPO_ROOT / "scripts"))
                from telegram_notifier import notify_published
                notify_published(
                    platform="Instagram",
                    channel="@sitcomvaultdaily",
                    title=target_item.get("title", ""),
                    url=pub_result["url"],
                    queue_index=target_item.get("queue_index")
                )
            except Exception as tel_err:
                log(f"[TELEGRAM] Notice: ping skipped ({tel_err})")

            commit_msg = f"chore(instagram): publish Reel #{target_item.get('queue_index', 1)} via Meta Graph API"
            commit_and_push_queue(QUEUE_FILE, commit_msg)
        else:
            log("[DRY RUN] Simulation complete! Queue was not modified.")

    except Exception as err:
        log(f"[PUBLISH ERROR] Failed to publish Reel via Meta Graph API: {err}")
        try:
            sys.path.append(str(REPO_ROOT / "scripts"))
            from telegram_notifier import notify_error
            notify_error(
                platform="Instagram",
                channel="@sitcomvaultdaily",
                error_msg=str(err),
                title=target_item.get("title", "Unknown")
            )
        except Exception as tel_err:
            log(f"[TELEGRAM] Warning: Error notification failed ({tel_err})")
        sys.exit(1)


if __name__ == "__main__":
    main()
