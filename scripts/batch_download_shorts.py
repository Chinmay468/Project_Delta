"""
Project Delta — Batch Marvel YouTube Shorts Curator & Downloader
Discovers, filters, and downloads 100 top-performing, viral Marvel YouTube Shorts
into D:\\Media\\shorts\\ with multi-part continuation support.
"""

import os
import sys
import re
import io
import time
import json
import random
import shutil
from typing import List, Dict, Any, Optional

# Ensure UTF-8 output on Windows console
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_SHORTS_DIR = r"D:\Media\shorts"
MANIFEST_PATH = os.path.join(DEFAULT_SHORTS_DIR, "manifest.json")

sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from download_short import download_youtube_short, normalize_youtube_url, fetch_short_metadata

# Category target plan with tailored search queries
MARVEL_CATEGORIES = {
    "01_iron_man_1": {
        "movie": "Iron Man 1 (2008)",
        "target": 5,
        "queries": [
            "iron man 1 cave escape part 1 #shorts",
            "iron man 1 mark 1 flamethrower #shorts",
            "iron man 1 jericho missile #shorts",
            "iron man 1 first flight test #shorts",
            "iron man 1 i am iron man press conference #shorts",
            "iron man 1 best scene viral #shorts",
        ],
    },
    "02_iron_man_2": {
        "movie": "Iron Man 2 (2010)",
        "target": 5,
        "queries": [
            "iron man 2 suitcase suit monaco part 1 #shorts",
            "iron man 2 suitcase armor #shorts",
            "iron man 2 senate hearing stark #shorts",
            "iron man 2 war machine drone battle #shorts",
            "iron man 2 creates new element #shorts",
        ],
    },
    "03_iron_man_3": {
        "movie": "Iron Man 3 (2013)",
        "target": 5,
        "queries": [
            "iron man 3 malibu mansion attack part 1 #shorts",
            "iron man 3 house party protocol #shorts",
            "iron man 3 barrel of monkeys sky rescue #shorts",
            "iron man 3 mark 42 suit up #shorts",
            "iron man 3 tony vs killian #shorts",
        ],
    },
    "04_avengers_1": {
        "movie": "The Avengers (2012)",
        "target": 6,
        "queries": [
            "the avengers we have a hulk #shorts",
            "the avengers hulk smashes loki part 1 #shorts",
            "the avengers iron man cap combo #shorts",
            "the avengers new york circle assemble #shorts",
            "the avengers iron man nuke sacrifice #shorts",
        ],
    },
    "05_avengers_ultron": {
        "movie": "Avengers: Age of Ultron (2015)",
        "target": 5,
        "queries": [
            "avengers age of ultron hulkbuster vs hulk part 1 #shorts",
            "avengers age of ultron lifting mjolnir #shorts",
            "avengers age of ultron ultron no strings on me #shorts",
            "avengers age of ultron quicksilver scene #shorts",
        ],
    },
    "06_avengers_infinity_war": {
        "movie": "Avengers: Infinity War (2018)",
        "target": 8,
        "queries": [
            "infinity war titan battle iron man vs thanos part 1 #shorts",
            "infinity war thor arrives wakanda bring me thanos #shorts",
            "infinity war doctor strange 14 million futures #shorts",
            "infinity war thanos snap dust scene #shorts",
            "infinity war cap holds thanos hand #shorts",
        ],
    },
    "07_avengers_endgame": {
        "movie": "Avengers: Endgame (2019)",
        "target": 10,
        "queries": [
            "endgame captain america lifts mjolnir part 1 #shorts",
            "endgame portals scene avengers assemble part 1 #shorts",
            "endgame i am iron man snap #shorts",
            "endgame scarlet witch vs thanos #shorts",
            "endgame iron man tony stark funeral #shorts",
        ],
    },
    "08_spiderman": {
        "movie": "Spider-Man Saga",
        "target": 18,
        "queries": [
            "spider man no way home 3 spidermen swing part 1 #shorts",
            "spider man no way home green goblin apartment fight #shorts",
            "spider man homecoming ferry scene iron man part 1 #shorts",
            "spider man far from home mysterio illusion trap #shorts",
            "spider man 2 train scene tobey maguire part 1 #shorts",
            "spider man andrew garfield saves mj #shorts",
        ],
    },
    "09_captain_america": {
        "movie": "Captain America: Winter Soldier & Civil War",
        "target": 10,
        "queries": [
            "captain america elevator fight before we start part 1 #shorts",
            "captain america winter soldier highway knife fight #shorts",
            "captain america civil war airport fight part 1 #shorts",
            "captain america civil war cap bucky vs iron man #shorts",
            "captain america civil war he is my friend so was i #shorts",
        ],
    },
    "10_thor": {
        "movie": "Thor: Ragnarok & MCU",
        "target": 8,
        "queries": [
            "thor ragnarok immigrant song bridge fight part 1 #shorts",
            "thor ragnarok arena thor vs hulk friend from work #shorts",
            "thor ragnarok loki falling 30 minutes #shorts",
            "thor ragnarok what are you god of hammers #shorts",
            "thor love and thunder gorr the god butcher #shorts",
        ],
    },
    "11_doctor_strange": {
        "movie": "Doctor Strange & Multiverse of Madness",
        "target": 8,
        "queries": [
            "doctor strange dormammu i have come to bargain part 1 #shorts",
            "doctor strange mirror dimension chase scene #shorts",
            "doctor strange multiverse of madness wanda illuminati #shorts",
            "doctor strange music notes fight #shorts",
            "doctor strange zombie strange darkhold #shorts",
        ],
    },
    "12_shang_chi": {
        "movie": "Shang-Chi and the Legend of the Ten Rings (2021)",
        "target": 6,
        "queries": [
            "shang chi bus fight scene part 1 #shorts",
            "shang chi scaffolding fight #shorts",
            "shang chi wenwu vs shang chi ten rings #shorts",
            "shang chi great protector dragon #shorts",
        ],
    },
    "13_deadpool_panther": {
        "movie": "Deadpool & Wolverine / Black Panther",
        "target": 6,
        "queries": [
            "deadpool wolverine opening fight bye bye bye #shorts",
            "deadpool wolverine car fight #shorts",
            "black panther killmonger is this your king part 1 #shorts",
            "black panther waterfall ritual fight #shorts",
            "black panther wakanda forever opening tribute #shorts",
        ],
    },
}


def detect_part_number(title: str) -> Optional[int]:
    """Detect if title indicates Part 1, Part 2, etc."""
    m = re.search(r"(?:part|pt)[\s.:_-]*([0-9]+)", title, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    m = re.search(r"([1-9])\s*/\s*([0-9])", title)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def search_candidate_shorts(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search YouTube for shorts matching query, filtered by duration and verticality."""
    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
        "extract_flat": "in_playlist",
    }

    candidates = []
    search_term = f"ytsearch{max_results}:{query}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(search_term, download=False)
            entries = res.get("entries", [])
            for entry in entries:
                if not entry:
                    continue
                dur = entry.get("duration") or 0
                # True Shorts are <= 65 seconds
                if dur <= 0 or dur > 65:
                    continue

                vid_id = entry.get("id")
                title = entry.get("title", "")
                views = entry.get("view_count") or 0

                candidates.append({
                    "id": vid_id,
                    "title": title,
                    "duration": dur,
                    "uploader": entry.get("uploader", "Unknown"),
                    "view_count": views,
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "part": detect_part_number(title),
                })
    except Exception as e:
        print(f"  [Warning] Search failed for query '{query}': {e}")

    return candidates


def generate_100_manifest(manifest_path: str = MANIFEST_PATH, category_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Query YouTube across all 13 categories (or a filtered category), rank by views,
    ensure continuation sequences, and build/update the master manifest.
    """
    print("=" * 70)
    print("  MARVEL VIRAL SHORTS DISCOVERY ENGINE (100 SHORTS)")
    print(f"  Target Destination: {DEFAULT_SHORTS_DIR}")
    print("=" * 70 + "\n")

    manifest = {}
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    manifest["target_count"] = 100
    manifest["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest["destination_root"] = DEFAULT_SHORTS_DIR
    if "categories" not in manifest:
        manifest["categories"] = {}

    total_discovered = 0
    seen_ids = set()
    for c_info in manifest["categories"].values():
        for s in c_info.get("shorts", []):
            seen_ids.add(s["id"])

    for cat_key, cat_data in MARVEL_CATEGORIES.items():
        if category_filter and category_filter not in cat_key:
            continue
        print(f"\nScanning Category [{cat_key}]: {cat_data['movie']} (Target: {cat_data['target']} shorts)")
        cat_candidates = []

        for q in cat_data["queries"]:
            print(f"  Searching: '{q}'...")
            res = search_candidate_shorts(q, max_results=8)
            for item in res:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    cat_candidates.append(item)
            time.sleep(1.5)  # Respectful pause

        # Sort candidates: prioritize multi-part continuation series and high view counts
        cat_candidates.sort(key=lambda x: (1 if x["part"] else 0, x["view_count"]), reverse=True)

        selected = cat_candidates[:cat_data["target"]]
        manifest["categories"][cat_key] = {
            "movie": cat_data["movie"],
            "target": cat_data["target"],
            "count": len(selected),
            "shorts": selected,
        }
        total_discovered += len(selected)
        print(f"  Selected {len(selected)}/{cat_data['target']} viral shorts for {cat_key}.")

    total_discovered = sum(len(c.get("shorts", [])) for c in manifest["categories"].values())
    manifest["total_discovered"] = total_discovered

    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Manifest generated successfully with {total_discovered} shorts!")
    print(f"Manifest saved to: {manifest_path}")
    return manifest


def batch_download_from_manifest(
    manifest_path: str = MANIFEST_PATH,
    category_filter: Optional[str] = None,
    limit: Optional[int] = None,
    delay_range: tuple = (2.0, 4.0),
) -> None:
    """
    Download shorts according to the manifest, storing into categorized subfolders in D:\\Media\\shorts\\.
    """
    if not os.path.isfile(manifest_path):
        print(f"[Error] Manifest file not found at {manifest_path}. Run generate_100_manifest first.")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print("=" * 70)
    print("  BATCH DOWNLOADING MARVEL SHORTS TO D:\\Media\\shorts")
    print("=" * 70 + "\n")

    downloaded_count = 0
    categories = manifest.get("categories", {})

    for cat_key, cat_info in categories.items():
        if category_filter and category_filter not in cat_key:
            continue

        cat_dir = os.path.join(DEFAULT_SHORTS_DIR, cat_key)
        os.makedirs(cat_dir, exist_ok=True)

        print(f"\n>>> Processing Category: {cat_info['movie']} ({cat_key})")
        shorts = cat_info.get("shorts", [])

        for idx, item in enumerate(shorts, 1):
            if limit and downloaded_count >= limit:
                print(f"\nReached download limit of {limit} shorts.")
                return

            vid_id = item["id"]
            title = item["title"]
            views = item.get("view_count", 0)

            # Determine destination filename
            clean_title = re.sub(r'[\\/*?:"<>|]', "", title)[:50].strip()
            dest_file = os.path.join(cat_dir, f"{cat_key}_{idx:02d}_{vid_id}.mp4")

            if os.path.isfile(dest_file) and os.path.getsize(dest_file) > 100_000:
                print(f"  [{idx}/{len(shorts)}] Already exists: {os.path.basename(dest_file)}")
                item["local_path"] = dest_file
                item["download_status"] = "cached"
                continue

            print(f"  [{idx}/{len(shorts)}] Downloading: \"{title}\" ({views:,} views)...")
            try:
                res = download_youtube_short(
                    url_or_id=item["url"],
                    output_dir=cat_dir,
                    filename=f"{cat_key}_{idx:02d}_{vid_id}",
                    quiet=True,
                )
                final_path = res["video_path"]
                file_size_mb = os.path.getsize(final_path) / (1024 * 1024)
                print(f"      Saved: {os.path.basename(final_path)} ({file_size_mb:.1f} MB, {res.get('width')}x{res.get('height')})")
                item["local_path"] = final_path
                item["download_status"] = "downloaded"
                item["file_size_mb"] = round(file_size_mb, 2)
                downloaded_count += 1
            except Exception as e:
                print(f"      [Failed] Error downloading {vid_id}: {e}")
                item["download_status"] = f"failed: {e}"

            # Polite randomized delay to avoid rate limiting
            pause_time = random.uniform(delay_range[0], delay_range[1])
            time.sleep(pause_time)

    # Update manifest with paths and download statuses
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n[DONE] Batch operation complete! Total newly downloaded: {downloaded_count}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Marvel YouTube Shorts Batch Discovery and Downloader")
    parser.add_argument("--discover", action="store_true", help="Generate 100-short manifest without downloading")
    parser.add_argument("--download", action="store_true", help="Download shorts listed in manifest")
    parser.add_argument("--category", type=str, default=None, help="Filter by category key (e.g. iron_man_1)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of shorts to download")
    args = parser.parse_args()

    if args.discover:
        generate_100_manifest(category_filter=args.category)
    elif args.download:
        batch_download_from_manifest(category_filter=args.category, limit=args.limit)
    else:
        # Default: generate manifest first if not present, then prompt user
        if not os.path.isfile(MANIFEST_PATH):
            print("No manifest found. Running discovery...")
            generate_100_manifest(category_filter=args.category)
        else:
            print(f"Existing manifest found at {MANIFEST_PATH}.")
            print("Run with --discover to regenerate, or --download to begin downloading.")
