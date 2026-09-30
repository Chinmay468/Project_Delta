"""
Browser-Based Instagram Session Authenticator
=============================================
Uses Playwright to open Instagram in Chrome, allowing you to log in smoothly.
Once logged in, it automatically captures all authentication cookies
(sessionid, ds_user_id, csrftoken, mid, etc.) and saves them to:
  config/instagram_session.json
"""

import sys
import json
import time
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from playwright.sync_api import sync_playwright

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
SESSION_FILE = CONFIG_DIR / "instagram_session.json"
STORAGE_STATE_FILE = CONFIG_DIR / "browser_storage_state.json"
USER_DATA_DIR = CONFIG_DIR / "browser_profile"


def login_via_browser():
    print("=" * 65)
    print("      INSTAGRAM ONE-CLICK BROWSER LOGIN HELPER")
    print("=" * 65)
    print("Launching Chromium browser window...")
    print("Please log into @sitcomvaultdaily in the browser window if prompted.")
    print("Once logged in and on the Instagram feed, this script will")
    print("automatically grab your cookies and save them permanently.")
    print("=" * 65 + "\n")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # Launch persistent browser context so logins stick
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")

        print("[WAIT] Waiting for Instagram login... (Take your time in the opened browser)")

        # Poll until sessionid cookie appears
        logged_in = False
        start_time = time.time()
        timeout_seconds = 300  # 5 minutes

        session_cookie = None
        user_id = None
        csrf_token = None

        while time.time() - start_time < timeout_seconds:
            cookies = context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in cookies if "instagram.com" in c.get("domain", "")}

            if "sessionid" in cookie_dict and "ds_user_id" in cookie_dict:
                session_cookie = cookie_dict["sessionid"]
                user_id = cookie_dict["ds_user_id"]
                csrf_token = cookie_dict.get("csrftoken", "")
                logged_in = True
                break

            time.sleep(2)

        if not logged_in:
            print("\n[TIMEOUT] Login took longer than 5 minutes or was cancelled.")
            context.close()
            return False

        print(f"\n[SUCCESS] Detected active session for User ID: {user_id}!")

        # Save Playwright storage state
        context.storage_state(path=str(STORAGE_STATE_FILE))
        print(f"[AUTH] Browser storage state saved to {STORAGE_STATE_FILE}")

        # Build instagrapi compatible session
        from instagrapi import Client
        cl = Client()
        cl.login_by_sessionid(session_cookie)
        cl.dump_settings(str(SESSION_FILE))
        print(f"[AUTH] Mobile session file saved to {SESSION_FILE}")

        time.sleep(1)
        context.close()

        print("\n" + "=" * 65)
        print("🎉 AUTHENTICATION COMPLETE & PERMANENTLY SAVED!")
        print("You can now run: python scripts/instagram_reels_uploader.py --post-next")
        print("=" * 65 + "\n")
        return True


if __name__ == "__main__":
    login_via_browser()
