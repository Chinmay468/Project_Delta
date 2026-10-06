"""
Facebook Reels & Video Uploader for Facebook Pages
==================================================
Directly publishes vertical reels/videos to Facebook Pages using Meta's official Graph API.
Zero browser emulation required - runs 100% headlessly on GitHub Actions and local machines.

Features:
- Official Meta Graph API Video Reels publishing (3-phase resumable upload).
- Fallback to standard Page Video API.
- Reads credentials from environment variables / GitHub Secrets:
    FB_PAGE_ID (Default: 61595194282867 - Sitcom Vault)
    FB_PAGE_ACCESS_TOKEN (Permanent Page Access Token)
- Seamless integration with data/instagram_queue.json.
- Verifies publishing status and generates direct Facebook Reel URLs.
"""

import os
import sys
import json
import time
import argparse
try:
    from dotenv import dotenv_values
except ImportError:
    def dotenv_values(path):
        return {}

import requests

# Force UTF-8 on Windows console
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"
ENV_FILE = CONFIG_DIR / ".env"
QUEUE_FILE = DATA_DIR / "instagram_queue.json"
MEDIA_BASE = Path(r"D:\Media\shorts")

DEFAULT_PAGE_ID = "1304317289439428"  # Sitcom Vault Page ID
GRAPH_API_VERSION = "v20.0"


def get_credentials():
    """Retrieves FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN from env or .env file."""
    env_vars = {}
    if ENV_FILE.exists():
        env_vars = dotenv_values(str(ENV_FILE))

    page_id = (
        os.environ.get("FB_PAGE_ID")
        or env_vars.get("FB_PAGE_ID")
        or DEFAULT_PAGE_ID
    ).strip()

    access_token = (
        os.environ.get("FB_PAGE_ACCESS_TOKEN")
        or env_vars.get("FB_PAGE_ACCESS_TOKEN")
        or ""
    ).strip()

    return page_id, access_token


def verify_page_access(page_id: str, access_token: str) -> dict:
    """Verifies that the Page Access Token is valid and can access the Page."""
    if not access_token:
        raise ValueError("Missing FB_PAGE_ACCESS_TOKEN! Please provide a valid Page Access Token.")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}"
    params = {
        "fields": "id,name,link,fan_count,verification_status",
        "access_token": access_token
    }
    resp = requests.get(url, params=params, timeout=15)
    data = resp.json()

    if resp.status_code != 200 or "error" in data:
        err_msg = data.get("error", {}).get("message", "Unknown Graph API error")
        raise RuntimeError(f"Facebook Graph API Error ({resp.status_code}): {err_msg}")

    return data


def resolve_video_path(item: dict) -> Path:
    """Finds the local or downloaded video file on disk."""
    filename = item.get("file_name") or Path(item.get("local_path", "")).name
    if not filename:
        return None

    # Check directly recorded path
    if item.get("local_path"):
        lp = Path(item["local_path"])
        if lp.exists() and lp.is_file():
            return lp

    # Check candidate search directories
    search_dirs = [
        Path("media_downloads"),
        Path("downloads"),
        Path("media"),
        Path("data"),
        REPO_ROOT / "media_downloads",
        REPO_ROOT / "downloads",
        MEDIA_BASE / "diepvo8265_reels",
        MEDIA_BASE / "himym",
        MEDIA_BASE,
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        cand = d / filename
        if cand.exists() and cand.is_file():
            return cand
        try:
            matches = list(d.rglob(filename))
            if matches:
                return matches[0]
        except Exception:
            pass

    return None


def upload_reel_to_facebook_page(page_id: str, access_token: str, video_path: Path, caption: str) -> dict:
    """
    Uploads a Reel to the specified Facebook Page using the 3-phase Video Reels API.
    Fallback to standard /videos endpoint if needed.
    """
    video_path = Path(video_path)
    file_size = video_path.stat().st_size
    print(f"[FB UPLOAD] Starting upload of '{video_path.name}' ({file_size / (1024*1024):.1f} MB)...")

    # PHASE 1: Initialize upload session
    init_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/video_reels"
    init_params = {
        "upload_phase": "start",
        "access_token": access_token
    }
    print("[FB UPLOAD] Phase 1: Requesting upload session from Meta Video Reels API...")
    init_resp = requests.post(init_url, data=init_params, timeout=30)
    init_data = init_resp.json()

    if init_resp.status_code != 200 or "video_id" not in init_data:
        err = init_data.get("error", {}).get("message", init_resp.text)
        print(f"[FB UPLOAD] Warning: /video_reels init failed ({err}). Trying standard /videos fallback...")
        return _fallback_upload_video(page_id, access_token, video_path, caption)

    video_id = init_data["video_id"]
    upload_url = init_data["upload_url"]
    print(f"[FB UPLOAD] Session created! Meta Video ID: {video_id}")

    # PHASE 2: Upload binary bytes
    print("[FB UPLOAD] Phase 2: Uploading video binary data...")
    upload_headers = {
        "Authorization": f"OAuth {access_token}",
        "offset": "0",
        "file_size": str(file_size)
    }
    with open(video_path, "rb") as f:
        upload_resp = requests.post(upload_url, headers=upload_headers, data=f, timeout=120)

    if upload_resp.status_code not in (200, 201):
        raise RuntimeError(f"Binary upload failed ({upload_resp.status_code}): {upload_resp.text}")

    print("[FB UPLOAD] Binary upload completed successfully!")

    # PHASE 3: Finalize and Publish
    print("[FB UPLOAD] Phase 3: Finalizing and publishing Reel...")
    finish_params = {
        "upload_phase": "finish",
        "access_token": access_token,
        "video_id": video_id,
        "video_state": "PUBLISHED",
        "description": caption
    }
    finish_resp = requests.post(init_url, data=finish_params, timeout=30)
    finish_data = finish_resp.json()

    if finish_resp.status_code != 200 or not finish_data.get("success", False):
        err = finish_data.get("error", {}).get("message", finish_resp.text)
        raise RuntimeError(f"Publishing failed ({finish_resp.status_code}): {err}")

    fb_url = f"https://www.facebook.com/reel/{video_id}"
    print(f"🎉 [FB SUCCESS] Reel is published to Facebook Page!")
    print(f"   Video ID: {video_id}")
    print(f"   URL:      {fb_url}")

    return {
        "video_id": video_id,
        "url": fb_url,
        "status": "published"
    }


def _fallback_upload_video(page_id: str, access_token: str, video_path: Path, caption: str) -> dict:
    """Fallback standard Page video upload (automatically rendered as Reel if 9:16 under 90s)."""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/videos"
    data = {
        "description": caption,
        "access_token": access_token
    }
    print("[FB UPLOAD] Performing direct /videos multipart upload...")
    with open(video_path, "rb") as f:
        files = {"source": (video_path.name, f, "video/mp4")}
        resp = requests.post(url, data=data, files=files, timeout=180)

    res_data = resp.json()
    if resp.status_code != 200 or "id" not in res_data:
        err = res_data.get("error", {}).get("message", resp.text)
        raise RuntimeError(f"Fallback upload failed ({resp.status_code}): {err}")

    video_id = res_data["id"]
    fb_url = f"https://www.facebook.com/{page_id}/videos/{video_id}"
    print(f"🎉 [FB SUCCESS] Video published via fallback! ID: {video_id} | URL: {fb_url}")
    return {
        "video_id": video_id,
        "url": fb_url,
        "status": "published"
    }


def post_facebook_reel(target_index: int = None) -> bool:
    """Loads queue, finds the target clip, and uploads it to Facebook Page."""
    page_id, access_token = get_credentials()
    if not access_token:
        print("[FB ERROR] FB_PAGE_ACCESS_TOKEN is not set.")
        print("           Please set FB_PAGE_ACCESS_TOKEN in your environment or GitHub Secrets.")
        return False

    # Check connection
    try:
        page_info = verify_page_access(page_id, access_token)
        print(f"[FB AUTH] Connected to Facebook Page: '{page_info.get('name')}' (ID: {page_info.get('id')})")
    except Exception as e:
        print(f"[FB AUTH ERROR] {e}")
        return False

    if not QUEUE_FILE.exists():
        print(f"[FB ERROR] Queue file not found: {QUEUE_FILE}")
        return False

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue_data = json.load(f)

    items = queue_data.get("queue", [])
    target_item = None

    if target_index is not None:
        matched = [it for it in items if it.get("queue_index") == target_index]
        if not matched:
            print(f"[FB ERROR] Queue item #{target_index} not found!")
            return False
        target_item = matched[0]
    else:
        # Pick the next item that hasn't been posted to Facebook yet
        pending_fb = [it for it in items if not it.get("facebook_video_id") and it.get("status") != "missing_file"]
        if not pending_fb:
            print("[FB QUEUE] No pending videos left for Facebook!")
            return False
        target_item = pending_fb[0]

    video_path = resolve_video_path(target_item)
    if not video_path or not video_path.exists():
        print(f"[FB ERROR] Video file not found for item #{target_item.get('queue_index')}: {target_item.get('title')}")
        return False

    caption = target_item.get("caption", target_item.get("title", ""))
    # Ensure Facebook hashtag
    if "#sitcomvault" not in caption.lower():
        caption += "\n\n#SitcomVault #Sitcoms #FunnyMoments"

    try:
        result = upload_reel_to_facebook_page(
            page_id=page_id,
            access_token=access_token,
            video_path=video_path,
            caption=caption
        )

        # Update queue item
        target_item["facebook_video_id"] = result["video_id"]
        target_item["facebook_url"] = result["url"]
        target_item["facebook_posted_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        # Save back to queue
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue_data, f, indent=2, ensure_ascii=False)

        print(f"[FB QUEUE] Saved Facebook upload details for Reel #{target_item.get('queue_index')} to queue!")

        # Send Telegram notification ping
        try:
            sys.path.append(str(REPO_ROOT / "scripts"))
            from telegram_notifier import notify_published
            notify_published(
                platform="Facebook",
                channel="Sitcom Vault (Facebook Page)",
                title=target_item.get("title", ""),
                url=result["url"],
                queue_index=target_item.get("queue_index")
            )
        except Exception as tel_err:
            print(f"[TELEGRAM] Notice: ping skipped ({tel_err})")

        return True

    except Exception as e:
        print(f"[FB UPLOAD ERROR] {e}")
        try:
            sys.path.append(str(REPO_ROOT / "scripts"))
            from telegram_notifier import notify_error
            notify_error(
                platform="Facebook",
                channel="Sitcom Vault (Facebook Page)",
                error_msg=str(e),
                title=target_item.get("title", "") if target_item else ""
            )
        except Exception:
            pass
        return False


def main():
    parser = argparse.ArgumentParser(description="Facebook Reels & Video Uploader for Facebook Pages")
    parser.add_argument("--post-index", type=int, help="Post a specific queue index to Facebook (e.g. 5)")
    parser.add_argument("--post-next", action="store_true", help="Post the next pending reel to Facebook")
    parser.add_argument("--status", action="store_true", help="Verify Page Access Token and connection to Facebook Page")

    args = parser.parse_args()

    if args.status:
        page_id, access_token = get_credentials()
        print("============================================================")
        print("             FACEBOOK PAGE CONNECTION STATUS")
        print("============================================================")
        print(f"  Target Page ID: {page_id}")
        if not access_token:
            print("  Access Token:   MISSING (Set FB_PAGE_ACCESS_TOKEN)")
            print("============================================================")
            sys.exit(1)
        try:
            info = verify_page_access(page_id, access_token)
            print(f"  Page Name:      {info.get('name')}")
            print(f"  Page ID:        {info.get('id')}")
            print(f"  Page Link:      {info.get('link')}")
            print("  Token Status:   VALID & AUTHORIZED ✅")
            print("============================================================")
        except Exception as e:
            print(f"  Token Error:    {e} ❌")
            print("============================================================")
            sys.exit(1)
        return

    if args.post_index is not None:
        success = post_facebook_reel(target_index=args.post_index)
        sys.exit(0 if success else 1)

    if args.post_next:
        success = post_facebook_reel()
        sys.exit(0 if success else 1)

    parser.print_help()


if __name__ == "__main__":
    main()
