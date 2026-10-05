"""
Telegram Notification Dispatcher for Automated Publishing Pipeline
===================================================================
Pings the user's Enquirer Service Telegram bot whenever a Short, Reel,
or Video is published (or fails) across any platform (YouTube, Instagram, Facebook).

Default Bot:
  Username: @enquirer_service_bot
  Chat ID:  1193729721
"""

import os
import sys
from datetime import datetime
import requests
from pathlib import Path
from dotenv import dotenv_values

# Force UTF-8 on Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
ENV_FILE = CONFIG_DIR / ".env"

# Fallback defaults from the user's Enquirer Service setup
DEFAULT_BOT_TOKEN = "8844066308:AAFZVtmKd18dHdGwre2o_59SvyYNb0Rg8Sg"
DEFAULT_CHAT_ID = "1193729721"


def get_telegram_config():
    """Gets Telegram BOT_TOKEN and CHAT_ID from env, .env, or default constants."""
    env_vars = {}
    if ENV_FILE.exists():
        try:
            env_vars = dotenv_values(str(ENV_FILE))
        except Exception:
            pass

    token = (
        os.environ.get("TELEGRAM_BOT_TOKEN")
        or env_vars.get("TELEGRAM_BOT_TOKEN")
        or DEFAULT_BOT_TOKEN
    ).strip()

    chat_id = (
        os.environ.get("TELEGRAM_CHAT_ID")
        or env_vars.get("TELEGRAM_CHAT_ID")
        or DEFAULT_CHAT_ID
    ).strip()

    return token, chat_id


def send_telegram_message(text: str, parse_mode: str = "Markdown") -> bool:
    """
    Sends a message to the configured Telegram chat.
    Safe and non-blocking: never raises exceptions that crash publishers.
    """
    token, chat_id = get_telegram_config()
    if not token or not chat_id:
        print("[TELEGRAM] Warning: Telegram token or chat_id is missing. Notification skipped.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            print("[TELEGRAM] Notification ping successfully delivered! 🚀")
            return True
        else:
            print(f"[TELEGRAM] Warning: API returned not ok: {data.get('description')}")
            # If markdown parsing fails due to special chars, retry in plain text
            if "can't parse entities" in data.get("description", "").lower():
                payload.pop("parse_mode", None)
                retry_resp = requests.post(url, json=payload, timeout=15)
                return retry_resp.json().get("ok", False)
            return False
    except Exception as e:
        print(f"[TELEGRAM] Warning: Failed to send Telegram message: {e}")
        return False


def notify_published(
    platform: str,
    channel: str,
    title: str,
    url: str,
    queue_index: int = None,
    extra_info: str = None
) -> bool:
    """
    Dispatches a formatted alert when a video is published successfully.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p IST")
    
    # Platform badge emoji
    p_lower = platform.lower()
    if "youtube" in p_lower:
        badge = "🔴 *YouTube Short Published*"
    elif "instagram" in p_lower:
        badge = "📸 *Instagram Reel Published*"
    elif "facebook" in p_lower:
        badge = "🔵 *Facebook Reel Published*"
    else:
        badge = f"🚀 *{platform} Video Published*"

    idx_str = f" (#{queue_index})" if queue_index else ""

    message = (
        f"{badge}\n\n"
        f"📺 *Channel:* `{channel}`\n"
        f"🎬 *Title:* {title}{idx_str}\n"
        f"🔗 *Watch Link:* {url}\n"
        f"⏰ *Published at:* `{now_str}`"
    )

    if extra_info:
        message += f"\nℹ️ _{extra_info}_"

    return send_telegram_message(message)


def notify_error(platform: str, channel: str, error_msg: str, title: str = None) -> bool:
    """Dispatches an alert if a daily publishing run encountered an issue."""
    now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p IST")
    message = (
        f"⚠️ *Publishing Alert / Notice*\n\n"
        f"📱 *Platform:* {platform}\n"
        f"📺 *Channel:* `{channel}`\n"
    )
    if title:
        message += f"🎬 *Target Clip:* {title}\n"
    message += (
        f"❌ *Issue:* `{error_msg}`\n"
        f"⏰ *Time:* `{now_str}`"
    )
    return send_telegram_message(message)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("[TELEGRAM] Sending test ping to Enquirer Service bot...")
        token, chat_id = get_telegram_config()
        print(f"  Bot Token: {token[:12]}...{token[-5:]}")
        print(f"  Chat ID:   {chat_id}")
        ok = send_telegram_message(
            "🔔 *Pipeline Notification System Active*\n\n"
            "This bot is now set up to ping you every day whenever a Reel or Short is published across:\n"
            "• 📸 Instagram (@sitcomvaultdaily)\n"
            "• 🔵 Facebook (Sitcom Vault Page)\n"
            "• 🔴 YouTube (The Asset Vault, Sitcom Vault, Just Nature)\n\n"
            "All systems operational! 🍿"
        )
        sys.exit(0 if ok else 1)

    print("Usage: python scripts/telegram_notifier.py --test")


if __name__ == "__main__":
    main()
