"""
Meta Instagram & Facebook Setup Verification Tool
==================================================
Tests your Meta Access Token, inspects permissions, checks token expiration,
and verifies the linked Instagram Business account.

Usage:
    python scripts/verify_meta_setup.py
    python scripts/verify_meta_setup.py <YOUR_META_TOKEN>
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Force UTF-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import dotenv_values
except ImportError:
    def dotenv_values(path):
        return {}

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
ENV_FILE = CONFIG_DIR / ".env"
DEFAULT_PAGE_ID = "1304317289439428"
GRAPH_VERSION = "v20.0"


def main():
    print("=" * 65)
    print("       META INSTAGRAM GRAPH API SETUP VERIFIER")
    print("=" * 65)

    # 1. Grab token
    token = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        token = sys.argv[1].strip()

    if not token:
        env_vars = {}
        if ENV_FILE.exists():
            env_vars = dotenv_values(str(ENV_FILE))
        token = (
            os.environ.get("INSTAGRAM_ACCESS_TOKEN")
            or os.environ.get("META_ACCESS_TOKEN")
            or os.environ.get("FB_PAGE_ACCESS_TOKEN")
            or env_vars.get("INSTAGRAM_ACCESS_TOKEN")
            or env_vars.get("META_ACCESS_TOKEN")
            or env_vars.get("FB_PAGE_ACCESS_TOKEN")
            or ""
        ).strip()

    if not token:
        print("\n❌ No Meta Access Token found.")
        print("   Please pass it as an argument or set INSTAGRAM_ACCESS_TOKEN in config/.env:\n")
        print("   python scripts/verify_meta_setup.py <YOUR_TOKEN>\n")
        sys.exit(1)

    print(f"Token: {token[:15]}...{token[-5:]} (length: {len(token)})")

    # 2. Inspect token
    print("\n[1] Inspecting Token Details & Expiration...")
    debug_url = f"https://graph.facebook.com/debug_token"
    debug_resp = requests.get(debug_url, params={"input_token": token, "access_token": token}, timeout=15)
    debug_data = debug_resp.json()

    if "data" in debug_data:
        info = debug_data["data"]
        app_id = info.get("app_id")
        type_ = info.get("type")
        is_valid = info.get("is_valid", False)
        expires_at = info.get("expires_at", 0)
        scopes = info.get("scopes", [])

        print(f"  • Valid:        {'YES ✅' if is_valid else 'NO ❌'}")
        print(f"  • App ID:       {app_id}")
        print(f"  • Token Type:   {type_}")

        if expires_at == 0:
            print("  • Expiration:   NEVER EXPIRES (Permanent System User Token) 🚀")
        else:
            exp_date = datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %H:%M:%S")
            print(f"  • Expiration:   Expires at {exp_date} (Temporary User Token)")

        print("\n[2] Checking Required Permissions:")
        required_scopes = [
            ("instagram_basic", "Basic Instagram account details access"),
            ("instagram_content_publish", "Publish Reels & Media to Instagram"),
            ("pages_show_list", "List and discover Facebook Pages"),
            ("pages_read_engagement", "Read Facebook Page engagement & status")
        ]
        all_scopes_ok = True
        for sc, desc in required_scopes:
            has_sc = sc in scopes
            status_icon = "✅" if has_sc else "❌ MISSING"
            if not has_sc:
                all_scopes_ok = False
            print(f"  {status_icon:10} {sc:28} ({desc})")

        if not all_scopes_ok:
            print("\n⚠️ Some permissions are missing. Please ensure your System User Token has all listed permissions.")
    else:
        print(f"  Notice: Could not inspect token via debug_token endpoint ({debug_data.get('error', {}).get('message', 'N/A')})")

    # 3. Test Facebook Page Connection
    page_id = DEFAULT_PAGE_ID
    print(f"\n[3] Querying Facebook Page (ID: {page_id})...")
    page_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}"
    page_resp = requests.get(
        page_url,
        params={"fields": "name,id,instagram_business_account,connected_instagram_account", "access_token": token},
        timeout=15
    )
    p_data = page_resp.json()

    if page_resp.status_code != 200 or "error" in p_data:
        err_msg = p_data.get("error", {}).get("message", "Unknown error")
        print(f"  ❌ Error querying page: {err_msg}")
        return

    page_name = p_data.get("name", "Unknown Page")
    print(f"  ✅ Facebook Page Found: '{page_name}' (ID: {page_id})")

    ig_acc = p_data.get("instagram_business_account") or p_data.get("connected_instagram_account")
    if not ig_acc or "id" not in ig_acc:
        print("  ❌ No Instagram Business Account connected to this Facebook Page.")
        print("     To connect: Go to Meta Business Suite -> Page Settings -> Instagram -> Connect Account.")
        return

    ig_id = ig_acc["id"]
    print(f"\n[4] Querying Linked Instagram Account (ID: {ig_id})...")
    ig_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{ig_id}"
    ig_resp = requests.get(
        ig_url,
        params={"fields": "username,name,profile_picture_url", "access_token": token},
        timeout=15
    )
    ig_data = ig_resp.json()

    if ig_resp.status_code != 200 or "error" in ig_data:
        err_msg = ig_data.get("error", {}).get("message", "Unknown error")
        print(f"  ❌ Error querying Instagram: {err_msg}")
        return

    ig_username = ig_data.get("username", "Unknown")
    print(f"  ✅ Instagram Account Verified: @{ig_username} (ID: {ig_id})")

    print("\n" + "=" * 65)
    print("🎉 ALL SYSTEMS OPERATIONAL! Your Meta setup is ready for Reels!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
