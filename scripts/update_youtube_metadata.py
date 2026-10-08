"""
Batch Update YouTube Metadata for Sitcom Vault Daily
=====================================================
Cleans and optimizes existing uploaded videos on YouTube:
- Removes [Part 1] / [Part 2] prefixes and adds #Shorts
- Purges Instagram hashtags (#reels, #explorepage) and copy ("Double-tap")
- Adds YouTube-native descriptions, subscriber CTAs, and rich SEO tags
"""

import sys
import io
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
TOKEN_PATH = CONFIG_DIR / "token_sitcom.json"

DEFAULT_TAGS = [
    "Shorts",
    "The Big Bang Theory",
    "Sheldon Cooper",
    "Big Bang Theory Funny Moments",
    "Sitcom",
    "Comedy",
    "TBBT",
    "Penny and Leonard",
    "Shamy",
    "Jim Parsons",
    "Sitcom Vault Daily",
    "Funny TV Clips"
]

METADATA_UPDATES = {
    "liF8VNrIlm4": {
        "title": "The Gift That Left Amy Speechless 🎁😂 #Shorts",
        "hook": "Sheldon gives Amy the most thoughtful and hilarious gift."
    },
    "EeHHQQcUQG8": {
        "title": "Sheldon Gives Amy His Most Precious Gift 😂 #Shorts",
        "hook": "Wait until you see how Sheldon prepares his gift for Amy."
    },
    "RjSO7OyvYOY": {
        "title": "Sheldon Convinces Penny Not To Dump Leonard 🤣 #Shorts",
        "hook": "Sheldon uses pure logic to stop Penny from breaking up with Leonard."
    },
    "dBjR00CcGMI": {
        "title": "How Sheldon Saved Leonard & Penny's Relationship 🥺 #Shorts",
        "hook": "The heartwarming conclusion to Sheldon saving Leonard and Penny."
    },
    "u9YxjYtGmew": {
        "title": "Amy Writes A Novel Inspired By Sheldon 😂 #Shorts #TheBigBangTheory",
        "hook": "Amy writes romantic fan-fiction and Sheldon turns out to be the inspiration."
    },
    "9WbPzb4iMjM": {
        "title": "Sheldon Gets Jealous When Kripke Hits On Amy 😂 #Shorts #TheBigBangTheory",
        "hook": "Sheldon Cooper actually gets jealous when Barry Kripke tries to flirt with Amy."
    },
    "1_fdUXTNC6Y": {
        "title": "Leonard Regrets Asking For It 🤣 #Shorts #TheBigBangTheory",
        "hook": "Classic Leonard moment where getting what he asked for backfires instantly."
    },
    "dAjI5xtpWdQ": {
        "title": "Amy Touches Sheldon's Heart On Christmas 😍 #Shorts #TheBigBangTheory",
        "hook": "Sheldon never celebrates holidays, but Amy manages to melt his cold exterior."
    },
    "oom5XTAyY8s": {
        "title": "When Sheldon Meets His Idol And Gets Shocked 🤣 #Shorts #TheBigBangTheory",
        "hook": "Leonard takes Sheldon to meet their hero, with completely unexpected results."
    },
    "imzysqbDacs": {
        "title": "Sheldon Says 'I Love You' For The First Time 😍 #Shorts #TheBigBangTheory",
        "hook": "One of the most touching moments in sitcom history: Sheldon confesses his feelings."
    },
    "2U6GnTTOGPo": {
        "title": "Sheldon & Amy's Birthday Plans Interrupted 🤣 #Shorts #TheBigBangTheory",
        "hook": "Sheldon and Amy's special birthday celebration takes a very chaotic turn."
    },
    "BPvJLNYwcUs": {
        "title": "Stuart Being Clueless Is Too Funny 😂 #Shorts #TheBigBangTheory",
        "hook": "Comic book store owner Stuart at his absolute peak awkward comedic self."
    },
    "AtGf346LZJw": {
        "title": "Sheldon's Itchy Sweater Punishment For Leonard 🤣 #Shorts #TheBigBangTheory",
        "hook": "Sheldon forces Leonard to wear an itchy sweater to prove a hilarious point."
    },
    "ymWBkurElpw": {
        "title": "Sheldon & Amy's Very First Kiss 🤣 #Shorts #TheBigBangTheory",
        "hook": "The unforgettable, hilarious first romantic kiss between Sheldon Cooper and Amy Farrah Fowler."
    }
}


def build_clean_description(title, hook):
    return (
        f"{title}\n\n"
        f"{hook} Classic comedy gold from The Big Bang Theory!\n\n"
        f"🔔 Subscribe to @SitcomVaultDaily for daily comedy sitcom shorts & funny TV moments!\n"
        f"💬 What is your all-time favorite Sheldon moment? Let us know below!\n\n"
        f"#Shorts #TheBigBangTheory #TBBT #SheldonCooper #Sitcom #Comedy #FunnyMoments"
    )


def update_all():
    print(f"[AUTH] Loading credentials from {TOKEN_PATH}...")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
    youtube = build("youtube", "v3", credentials=creds)

    print(f"\n[START] Updating metadata for {len(METADATA_UPDATES)} existing uploads...\n")
    updated_count = 0

    for vid_id, data in METADATA_UPDATES.items():
        try:
            res = youtube.videos().list(part="snippet", id=vid_id).execute()
            if not res.get("items"):
                print(f"  ❌ [{vid_id}] Video not found on YouTube.")
                continue

            snippet = res["items"][0]["snippet"]
            new_title = data["title"]
            new_desc = build_clean_description(new_title, data["hook"])
            
            snippet["title"] = new_title[:100]
            snippet["description"] = new_desc
            snippet["tags"] = DEFAULT_TAGS
            snippet["categoryId"] = "24"  # Entertainment

            youtube.videos().update(
                part="snippet",
                body={"id": vid_id, "snippet": snippet}
            ).execute()

            print(f"  ✅ [{vid_id}] Updated: {new_title}")
            updated_count += 1

        except Exception as e:
            print(f"  ❌ [{vid_id}] Failed to update: {e}")

    print(f"\n[DONE] Successfully updated {updated_count}/{len(METADATA_UPDATES)} videos on YouTube!")


if __name__ == "__main__":
    update_all()
