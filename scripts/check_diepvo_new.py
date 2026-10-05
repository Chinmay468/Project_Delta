import sys
import io
import json
from pathlib import Path
import yt_dlp

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def check_channel():
    channel_url = "https://www.youtube.com/@diepvo8265/shorts"
    print(f"Checking {channel_url}...")
    
    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        res = ydl.extract_info(channel_url, download=False)
        entries = res.get("entries", [])
    
    print(f"Found {len(entries)} shorts currently on channel.")
    
    # Load existing manifest
    manifest_file = Path(r"D:\Media\shorts\diepvo8265\manifest.json")
    known_ids = set()
    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for s in data.get("shorts", []):
            vid = s.get("youtube_id") or s.get("id")
            if vid:
                known_ids.add(vid)
    
    # Check queue file as well
    queue_file = Path(r"D:\Projects\movie-shorts-pipeline\movie-shorts-pipeline\data\instagram_queue.json")
    if queue_file.exists():
        with open(queue_file, "r", encoding="utf-8") as f:
            qdata = json.load(f)
        for item in qdata.get("queue", []):
            item_id = item.get("id", "").split("_")[0]
            if item_id:
                known_ids.add(item_id)

    # Check files on disk
    target_dir = Path(r"D:\Media\shorts\diepvo8265")
    if target_dir.exists():
        for p in target_dir.glob("*.mp4"):
            for e in entries:
                vid = e.get("id")
                if vid and vid in p.name:
                    known_ids.add(vid)

    reels_dir = Path(r"D:\Media\shorts\diepvo8265_reels")
    if reels_dir.exists():
        for p in reels_dir.glob("*.mp4"):
            for e in entries:
                vid = e.get("id")
                if vid and vid in p.name:
                    known_ids.add(vid)

    print(f"Known video IDs already in local library: {len(known_ids)}")
    
    new_shorts = []
    for idx, e in enumerate(entries, 1):
        vid_id = e.get("id")
        title = e.get("title", "")
        if vid_id not in known_ids:
            new_shorts.append({
                "index_on_channel": idx,
                "id": vid_id,
                "title": title,
                "url": f"https://www.youtube.com/shorts/{vid_id}"
            })
            
    print(f"\n==================================================")
    print(f"NEW SHORTS FOUND: {len(new_shorts)}")
    print(f"==================================================")
    for s in new_shorts:
        print(f"  #{s['index_on_channel']:02d} | ID: {s['id']} | Title: {s['title']}")
    print(f"==================================================\n")
        
    return new_shorts, entries

if __name__ == "__main__":
    check_channel()
