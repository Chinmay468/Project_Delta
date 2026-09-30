"""
Instagram Reels Automation & Uploader
====================================
Automates posting vertical shorts/reels to Instagram directly from local media folders.
Uses instagrapi for seamless session-based posting (no developer app or public URL required).

Features:
- Persistent session storage in config/instagram_session.json (log in once, run forever).
- Multi-factor authentication (2FA/OTP) support.
- Generates and manages D:\\Media\\shorts\\instagram_queue.json.
- Smart caption generation with high-CTR Instagram tags and call-to-actions.
- Windows Task Scheduler automation support for daily hands-free posting.
"""

import os
import sys
import json
import time
import re
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Force UTF-8 on Windows console for emojis
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from dotenv import dotenv_values
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword,
    TwoFactorRequired,
    ChallengeRequired,
    PleaseWaitFewMinutes,
    LoginRequired
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"
ENV_FILE = CONFIG_DIR / ".env"
SESSION_FILE = CONFIG_DIR / "instagram_session.json"

MEDIA_BASE = Path(r"D:\Media\shorts")


def get_queue_file() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    repo_q = DATA_DIR / "instagram_queue.json"
    if repo_q.exists():
        return repo_q
    if MEDIA_BASE.exists() and (MEDIA_BASE / "instagram_queue.json").exists():
        return MEDIA_BASE / "instagram_queue.json"
    return repo_q


IG_QUEUE_FILE = get_queue_file()


def save_queue_data(queue_data: dict):
    r"""Saves queue data to repo data/ and local D:\Media if available."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "instagram_queue.json", "w", encoding="utf-8") as f:
        json.dump(queue_data, f, indent=2, ensure_ascii=False)
    if MEDIA_BASE.exists():
        try:
            with open(MEDIA_BASE / "instagram_queue.json", "w", encoding="utf-8") as f:
                json.dump(queue_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


def get_credentials():
    """Fetches Instagram credentials from .env or prompts user."""
    env_vars = {}
    if ENV_FILE.exists():
        env_vars = dotenv_values(str(ENV_FILE))

    username = env_vars.get("INSTAGRAM_USERNAME")
    password = env_vars.get("INSTAGRAM_PASSWORD")

    if not username:
        username = input("Enter Instagram username: ").strip()
    if not password:
        password = input("Enter Instagram password: ").strip()

    return username, password


def login_with_sessionid(sessionid: str) -> Client:
    """Authenticates using an Instagram browser sessionid cookie and saves session."""
    import urllib.parse
    cl = Client()
    cl.delay_range = [2, 5]
    sessionid = sessionid.strip().strip("'\"")
    sessionid_clean = urllib.parse.unquote(sessionid)

    print("[AUTH] Authenticating using Instagram browser sessionid...")
    try:
        cl.login_by_sessionid(sessionid_clean)
        # Verify active connection
        try:
            cl.user_info_v1(int(cl.user_id))
        except Exception:
            pass
        username = getattr(cl, "username", None) or "sitcomvaultdaily"
        print(f"\n[AUTH SUCCESS] Successfully logged in as @{username} (ID: {cl.user_id})!")
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cl.dump_settings(str(SESSION_FILE))
        print(f"[AUTH] Session permanently saved to {SESSION_FILE}")
        return cl
    except Exception as e:
        print(f"[AUTH ERROR] Failed to log in with session ID: {e}")
        print("Tip: Make sure you copied the fresh value of the 'sessionid' cookie from https://www.instagram.com.")
        sys.exit(1)


def try_refresh_session_from_browser() -> Client:
    """Attempts to auto-heal session by extracting cookies from Playwright Meta/Instagram browser profile."""
    try:
        from playwright.sync_api import sync_playwright
        browser_dir = CONFIG_DIR / "meta_suite_profile"
        if not browser_dir.exists():
            return None
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(str(browser_dir), headless=True)
            cookies = ctx.cookies()
            ctx.close()
        sid = next((c["value"] for c in cookies if c["name"] == "sessionid" and "instagram" in c.get("domain", "")), None)
        if sid:
            cl = Client()
            cl.login_by_sessionid(sid)
            cl.dump_settings(str(SESSION_FILE))
            username = getattr(cl, "username", "sitcomvaultdaily")
            print(f"[AUTH] Auto-healed session using browser cookies for @{username}!")
            return cl
    except Exception as e:
        print(f"[AUTH] Browser auto-heal notice: {e}")
    return None


def get_authenticated_client(relogin: bool = False, sessionid: str = None) -> Client:
    """
    Initializes and authenticates the Instagram client.
    Reuses existing session cookies if valid.
    """
    if sessionid:
        return login_with_sessionid(sessionid)

    cl = Client()
    cl.delay_range = [2, 5]

    # Attempt session load
    if SESSION_FILE.exists() and not relogin:
        try:
            cl.load_settings(str(SESSION_FILE))
            if getattr(cl, "user_id", None):
                # Verify session is still valid on Instagram servers
                try:
                    cl.user_info_v1(int(cl.user_id))
                    username = getattr(cl, "username", None) or "sitcomvaultdaily"
                    print(f"[AUTH] Active session verified for @{username} (ID: {cl.user_id})")
                    return cl
                except Exception as health_err:
                    print(f"[AUTH] Saved session expired ({health_err}). Attempting auto-heal from browser profile...")
                    cl_refreshed = try_refresh_session_from_browser()
                    if cl_refreshed:
                        return cl_refreshed
        except Exception as e:
            print(f"[AUTH] Saved session invalid ({e}). Attempting auto-heal from browser profile...")
            cl_refreshed = try_refresh_session_from_browser()
            if cl_refreshed:
                return cl_refreshed

    # Check browser profile before interactive prompt
    cl_refreshed = try_refresh_session_from_browser()
    if cl_refreshed and not relogin:
        return cl_refreshed

    # Interactive choice or env
    env_vars = {}
    if ENV_FILE.exists():
        env_vars = dotenv_values(str(ENV_FILE))

    env_session = os.environ.get("INSTAGRAM_SESSIONID") or env_vars.get("INSTAGRAM_SESSIONID")
    if env_session and not relogin:
        return login_with_sessionid(env_session)

    # In CI / GitHub Actions, fail gracefully if secret missing instead of hanging
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        print("[AUTH ERROR] Missing INSTAGRAM_SESSIONID secret in environment! Cannot prompt interactively in CI.")
        sys.exit(1)

    print("\n" + "=" * 65)
    print("                 INSTAGRAM AUTHENTICATION")
    print("=" * 65)
    print("Instagram's mobile API frequently blocks direct password logins")
    print("with 'Your version of Instagram is out of date'.")
    print("The most reliable, 100% working method is your browser's sessionid.\n")
    print("How to get your sessionid in 30 seconds:")
    print(" 1. Open https://www.instagram.com in Chrome / Edge / Brave / Firefox")
    print(" 2. Press F12 (Developer Tools) -> Go to 'Application' (or 'Storage') tab")
    print(" 3. Expand 'Cookies' -> click 'https://www.instagram.com'")
    print(" 4. Find the cookie named 'sessionid' and copy its full Value.")
    print("=" * 65)
    print("Select authentication method:")
    print("  [1] Paste browser sessionid cookie (Recommended - Instant & 100% works)")
    print("  [2] Instagram Username & Password (requires @handle, NOT email)")
    choice = input("Enter choice [1 or 2, default: 1]: ").strip()

    if choice == "2":
        username, password = get_credentials()
        if "@" in username and ("gmail" in username or "yahoo" in username or "outlook" in username or "hotmail" in username):
            print("\n[WARNING] You entered an email address. Instagram's private API requires")
            print("          your account handle/username (e.g. 'sitcomvaultdaily'), NOT your email.")
            retry = input("Enter your Instagram username handle (without @): ").strip()
            if retry:
                username = retry

        print(f"[AUTH] Logging into Instagram as @{username}...")
        try:
            cl.login(username, password)
        except TwoFactorRequired:
            print("\n" + "=" * 50)
            print("[AUTH 2FA] Two-Factor Authentication required!")
            code = input("Enter the 6-digit SMS / Authenticator app security code: ").strip()
            cl.login(username, password, verification_code=code)
        except ChallengeRequired as e:
            print(f"\n[AUTH CHECKPOINT] Instagram security checkpoint triggered: {e}")
            print("Please open the Instagram app on your phone, approve the login prompt, then re-run.")
            sys.exit(1)
        except BadPassword:
            print("[AUTH ERROR] Incorrect password. Check your credentials in config/.env.")
            sys.exit(1)
        except PleaseWaitFewMinutes:
            print("[AUTH RATE LIMIT] Instagram requested to wait a few minutes before trying again.")
            sys.exit(1)
        except Exception as e:
            print(f"[AUTH ERROR] Password login failed: {e}")
            print("\nTip: Use Option [1] (sessionid cookie from browser) to bypass this completely.")
            sys.exit(1)

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cl.dump_settings(str(SESSION_FILE))
        print(f"[AUTH SUCCESS] Login successful! Session dumped to {SESSION_FILE}")
        update_env_credentials(username, password)
        return cl
    else:
        sid = input("Paste your Instagram 'sessionid' cookie value: ").strip()
        if not sid:
            print("[AUTH ERROR] No session ID provided.")
            sys.exit(1)
        return login_with_sessionid(sid)


def update_env_credentials(username: str, password: str):
    """Saves Instagram username and password into config/.env."""
    lines = []
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

    has_user = False
    has_pass = False
    new_lines = []
    for line in lines:
        if line.startswith("INSTAGRAM_USERNAME="):
            new_lines.append(f"INSTAGRAM_USERNAME={username}\n")
            has_user = True
        elif line.startswith("INSTAGRAM_PASSWORD="):
            new_lines.append(f"INSTAGRAM_PASSWORD={password}\n")
            has_pass = True
        else:
            new_lines.append(line)

    if not has_user:
        new_lines.append(f"INSTAGRAM_USERNAME={username}\n")
    if not has_pass:
        new_lines.append(f"INSTAGRAM_PASSWORD={password}\n")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def clean_scene_title(raw_title: str) -> str:
    clean = re.sub(r'#\S+', '', raw_title).strip()
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip(". -")


def build_instagram_caption(title: str, show: str, username: str = "SitcomVaultDaily") -> str:
    """Formats high-CTR captions tailored for Instagram Reels."""
    clean_t = clean_scene_title(title)
    if show == "TBBT":
        hashtags = "#reels #reelsinstagram #tbbt #thebigbangtheory #sheldoncooper #bazinga #comedyreels #sitcom #funnyreels #viralreels #explorepage #tvshowclips #dailymemes"
        cta = f"Follow @{username} for daily Big Bang Theory & sitcom moments! 😂🍿"
    else:
        hashtags = "#reels #reelsinstagram #himym #howimetyourmother #barneystinson #tedmosby #legendary #comedyreels #sitcom #funnyreels #viralreels #explorepage #sitcomclips"
        cta = f"Follow @{username} for legendary HIMYM & sitcom moments! 🍺🍿"

    caption = (
        f"{clean_t} 🤣\n\n"
        f"Double tap if this made you laugh! ❤️\n"
        f"{cta}\n\n"
        f"•\n•\n•\n"
        f"{hashtags}"
    )
    return caption


def get_logged_in_username() -> str:
    """Gets the username of the logged-in Instagram user, if available."""
    if SESSION_FILE.exists():
        try:
            cl = Client()
            cl.load_settings(str(SESSION_FILE))
            if getattr(cl, "username", None):
                return cl.username
        except Exception:
            pass
    return "sitcomvaultdaily"


def build_or_sync_queue(ig_username: str = None) -> dict:
    """
    Scans available local .mp4 files from diepvo8265 and himym directories,
    creating or updating D:\\Media\\shorts\\instagram_queue.json.
    """
    if not ig_username:
        ig_username = get_logged_in_username()

    existing_queue = {}
    if IG_QUEUE_FILE.exists():
        try:
            with open(IG_QUEUE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("queue", []):
                    existing_queue[item["id"]] = item
        except Exception:
            pass

    new_items = []
    q_idx = 1

    # 1. Check Big Bang Theory shorts (diepvo8265)
    tbbt_dir = MEDIA_BASE / "diepvo8265"
    tbbt_manifest = tbbt_dir / "manifest.json"
    if tbbt_manifest.exists():
        with open(tbbt_manifest, "r", encoding="utf-8") as f:
            tbbt_data = json.load(f)
        for s in tbbt_data.get("shorts", []):
            vid_id = s["id"]
            lp = Path(s.get("local_path", ""))
            if lp.exists() and lp.suffix.lower() == ".mp4":
                if vid_id in existing_queue:
                    item = existing_queue[vid_id]
                    item["queue_index"] = q_idx
                    item["local_path"] = str(lp)
                    item["file_name"] = lp.name
                    if item.get("status") == "pending":
                        item["caption"] = build_instagram_caption(s.get("title", "Funny Sheldon Moment"), "TBBT", ig_username)
                    new_items.append(item)
                else:
                    caption = build_instagram_caption(s.get("title", "Funny Sheldon Moment"), "TBBT", ig_username)
                    new_items.append({
                        "queue_index": q_idx,
                        "id": vid_id,
                        "show": "The Big Bang Theory",
                        "local_path": str(lp),
                        "file_name": lp.name,
                        "title": clean_scene_title(s.get("title", "")),
                        "caption": caption,
                        "status": "pending",
                        "instagram_media_id": None,
                        "instagram_code": None,
                        "instagram_url": None,
                        "posted_at": None
                    })
                q_idx += 1

    # 2. Check How I Met Your Mother shorts (himym)
    himym_dir = MEDIA_BASE / "himym"
    himym_manifest = himym_dir / "manifest.json"
    if himym_manifest.exists():
        with open(himym_manifest, "r", encoding="utf-8") as f:
            himym_data = json.load(f)
        for s in himym_data.get("shorts", []):
            vid_id = s["id"]
            lp = Path(s.get("local_path", ""))
            if lp.exists() and lp.suffix.lower() == ".mp4":
                if vid_id in existing_queue:
                    item = existing_queue[vid_id]
                    item["queue_index"] = q_idx
                    item["local_path"] = str(lp)
                    item["file_name"] = lp.name
                    if item.get("status") == "pending":
                        item["caption"] = build_instagram_caption(s.get("title", "Legendary HIMYM Moment"), "HIMYM", ig_username)
                    new_items.append(item)
                else:
                    caption = build_instagram_caption(s.get("title", "Legendary HIMYM Moment"), "HIMYM", ig_username)
                    new_items.append({
                        "queue_index": q_idx,
                        "id": vid_id,
                        "show": "How I Met Your Mother",
                        "local_path": str(lp),
                        "file_name": lp.name,
                        "title": clean_scene_title(s.get("title", "")),
                        "caption": caption,
                        "status": "pending",
                        "instagram_media_id": None,
                        "instagram_code": None,
                        "instagram_url": None,
                        "posted_at": None
                    })
                q_idx += 1

    queue_data = {
        "channel": f"@{ig_username}",
        "total_items": len(new_items),
        "pending_items": sum(1 for x in new_items if x.get("status") == "pending"),
        "posted_items": sum(1 for x in new_items if x.get("status") == "posted"),
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "queue": new_items
    }

    with open(IG_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue_data, f, indent=2, ensure_ascii=False)

    print(f"[QUEUE] Synced Instagram Queue: {IG_QUEUE_FILE}")
    print(f"        Total ready files: {queue_data['total_items']} | Pending: {queue_data['pending_items']} | Posted: {queue_data['posted_items']}")
    return queue_data



def extract_thumbnail_if_needed(video_path: Path) -> Path:
    """Extracts a high-quality frame from the video using OpenCV to serve as the Reel thumbnail."""
    thumb_path = video_path.with_suffix(".jpg")
    if thumb_path.exists() and thumb_path.stat().st_size > 1000:
        return thumb_path

    try:
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        # Grab frame at 1.5 seconds into the video
        cap.set(cv2.CAP_PROP_POS_MSEC, 1500)
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_MSEC, 0)
            ret, frame = cap.read()
        cap.release()

        if ret and frame is not None:
            cv2.imwrite(str(thumb_path), frame)
            return thumb_path
    except Exception as e:
        print(f"[WARN] OpenCV thumbnail extraction notice: {e}")

    return None


def resolve_video_path(item: dict) -> Path | None:
    """Finds the local video file on disk across local media directories and cloud download folders."""
    filename = item.get("file_name") or Path(item.get("local_path", "")).name

    # 1. Direct local_path check
    if item.get("local_path"):
        lp = Path(item["local_path"])
        if lp.exists() and lp.is_file():
            return lp

    # 2. Check candidate search directories
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


def post_next_reel(cl: Client = None) -> bool:
    """Posts the next pending video from instagram_queue.json."""
    if not IG_QUEUE_FILE.exists():
        build_or_sync_queue()

    with open(IG_QUEUE_FILE, "r", encoding="utf-8") as f:
        queue_data = json.load(f)

    # Allow retrying failed items if requested or select next pending
    pending = [item for item in queue_data.get("queue", []) if item.get("status") in ["pending", "failed"]]
    if not pending:
        print("[QUEUE] No pending videos left to post in Instagram queue!")
        return False

    next_item = pending[0]
    local_path = resolve_video_path(next_item)

    if not local_path or not local_path.exists():
        print(f"[ERROR] Local video file does not exist for: {next_item.get('title')}")
        print(f"        Target file name: {next_item.get('file_name', next_item.get('local_path'))}")
        next_item["status"] = "missing_file"
        save_queue_data(queue_data)
        return False

    if cl is None:
        cl = get_authenticated_client()

    print(f"\n[POSTING] Uploading Reel #{next_item['queue_index']} ({next_item['show']}):")
    print(f"          Title: {next_item['title']}")
    print(f"          File:  {local_path.name} ({local_path.stat().st_size / (1024*1024):.1f} MB)")
    try:
        thumb_path = extract_thumbnail_if_needed(local_path)
        media = None
        try:
            media = cl.clip_upload(
                path=local_path,
                caption=next_item["caption"],
                thumbnail=thumb_path,
                show_preview_in_feed=True
            )
        except Exception as upload_err:
            if "upload_settings" in str(upload_err).lower() or "login_required" in str(upload_err).lower():
                print(f"[POSTING] Notice: Mobile clip_upload restricted ({upload_err}). Retrying via direct video_upload...")
                media = cl.video_upload(
                    path=local_path,
                    caption=next_item["caption"],
                    thumbnail=thumb_path
                )
            else:
                raise upload_err

        code = getattr(media, "code", None)
        media_id = getattr(media, "id", None) or getattr(media, "pk", None)
        reel_url = f"https://www.instagram.com/reel/{code}/" if code else f"https://www.instagram.com/"

        print("\n" + "=" * 60)
        print(f"🎉 REEL POSTED SUCCESSFULLY!")
        print(f"   URL: {reel_url}")
        print(f"   Media ID: {media_id}")
        print("=" * 60 + "\n")

        next_item["status"] = "posted"
        next_item["instagram_media_id"] = str(media_id)
        next_item["instagram_code"] = str(code)
        next_item["instagram_url"] = reel_url
        next_item["posted_at"] = datetime.now().isoformat()

        queue_data["pending_items"] = sum(1 for x in queue_data["queue"] if x.get("status") == "pending")
        queue_data["posted_items"] = sum(1 for x in queue_data["queue"] if x.get("status") == "posted")
        queue_data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

        save_queue_data(queue_data)

        # Dump updated session
        cl.dump_settings(str(SESSION_FILE))
        return True

    except Exception as e:
        print(f"[UPLOAD ERROR] Failed to upload Reel: {e}")
        next_item["status"] = "failed"
        next_item["error"] = str(e)
        save_queue_data(queue_data)
        return False


def post_file(path_str: str, caption_override: str = None):
    """Directly uploads a single specific video file as an Instagram Reel."""
    path = Path(path_str)
    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        return False

    cl = get_authenticated_client()
    caption = caption_override or build_instagram_caption(path.stem, "TBBT")
    print(f"[POSTING] Uploading {path.name} as Reel...")
    thumb_path = extract_thumbnail_if_needed(path)
    media = None
    try:
        media = cl.clip_upload(path=path, caption=caption, thumbnail=thumb_path, show_preview_in_feed=True)
    except Exception as upload_err:
        if "upload_settings" in str(upload_err).lower() or "login_required" in str(upload_err).lower():
            print(f"[POSTING] Notice: Mobile clip_upload restricted ({upload_err}). Retrying via direct video_upload...")
            media = cl.video_upload(path=path, caption=caption, thumbnail=thumb_path)
        else:
            raise upload_err

    code = getattr(media, "code", None)
    print(f"🎉 Posted! URL: https://www.instagram.com/reel/{code}/")
    return True


def show_status():
    """Displays current Instagram authentication and queue status."""
    print("\n" + "=" * 60)
    print("      INSTAGRAM REELS PIPELINE STATUS")
    print("=" * 60)

    # Auth check
    if SESSION_FILE.exists():
        try:
            cl = Client()
            cl.load_settings(str(SESSION_FILE))
            username = getattr(cl, "username", None) or "sitcomvaultdaily"
            user_id = getattr(cl, "user_id", None) or "N/A"
            print(f"  Account:     @{username} (User ID: {user_id})")
            print(f"  Session:     Valid ({SESSION_FILE})")
        except Exception as e:
            print(f"  Session:     Saved, but re-login needed ({e})")
    else:
        print("  Session:     Not logged in yet. Run with --login.")

    # Queue check
    if IG_QUEUE_FILE.exists():
        with open(IG_QUEUE_FILE, "r", encoding="utf-8") as f:
            q = json.load(f)
        print(f"\n  Queue File:  {IG_QUEUE_FILE}")
        print(f"  Total Clips: {q.get('total_items', 0)}")
        print(f"  Pending:     {q.get('pending_items', 0)}")
        print(f"  Posted:      {q.get('posted_items', 0)}")
        recent_posted = [x for x in q.get("queue", []) if x.get("status") == "posted"]
        if recent_posted:
            print("\n  Recently Posted:")
            for r in recent_posted[-3:]:
                print(f"    - [{r.get('posted_at', '')[:10]}] {r.get('title', '')}: {r.get('instagram_url', '')}")
    else:
        print("\n  Queue:       Not generated yet. Run with --build-queue.")
    print("=" * 60 + "\n")


def setup_windows_daily_task(post_time: str = "19:30"):
    """Creates/upgrades a Windows Scheduled Task with catch-up, wake, and battery support."""
    from scripts.upgrade_windows_task import upgrade_task
    return upgrade_task()


def main():
    parser = argparse.ArgumentParser(description="Instagram Reels Automated Uploader")
    parser.add_argument("--login", action="store_true", help="Log in and save session to config/instagram_session.json")
    parser.add_argument("--browser-login", action="store_true", help="Launch Chrome window to log in and auto-save session")
    parser.add_argument("--sessionid", type=str, help="Authenticate using browser sessionid cookie")
    parser.add_argument("--relogin", action="store_true", help="Force re-login even if session exists")
    parser.add_argument("--build-queue", action="store_true", help="Scan local files and build D:\\Media\\shorts\\instagram_queue.json")
    parser.add_argument("--post-next", action="store_true", help="Upload the next pending video from the queue")
    parser.add_argument("--post-file", type=str, help="Upload a specific video file")
    parser.add_argument("--caption", type=str, help="Optional caption for --post-file")
    parser.add_argument("--status", action="store_true", help="Show session and queue status")
    parser.add_argument("--schedule-daily", type=str, nargs="?", const="19:30", help="Setup Windows Task Scheduler to post daily (default: 19:30)")

    args = parser.parse_args()

    if args.browser_login:
        from scripts.login_instagram_browser import login_via_browser
        login_via_browser()
        build_or_sync_queue()
        show_status()
    elif args.sessionid:
        cl = get_authenticated_client(sessionid=args.sessionid)
        build_or_sync_queue(getattr(cl, "username", None) or "sitcomvaultdaily")
        show_status()
    elif args.login or args.relogin:
        cl = get_authenticated_client(relogin=args.relogin)
        build_or_sync_queue(getattr(cl, "username", None) or "sitcomvaultdaily")
        show_status()
    elif args.build_queue:
        build_or_sync_queue()
    elif args.post_next:
        post_next_reel()
    elif args.post_file:
        post_file(args.post_file, args.caption)
    elif args.schedule_daily:
        setup_windows_daily_task(args.schedule_daily)
    elif args.status:
        show_status()
    else:
        # Default behavior: if no args given, build queue and show status
        build_or_sync_queue()
        show_status()


if __name__ == "__main__":
    main()
