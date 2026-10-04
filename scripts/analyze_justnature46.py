import sys
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import json
from instagrapi import Client

os.makedirs("scratch", exist_ok=True)
cl = Client()
try:
    cl.load_settings("config/instagram_session.json")
    user_id = cl.user_id_from_username("justnature46")
    user = cl.user_info(user_id)
    print(f"Loaded @{user.username} with {user.media_count} posts.")
    
    # fetch 50 posts
    medias = cl.user_medias(user_id, amount=60)
    data = []
    for idx, m in enumerate(medias, 1):
        cap = (m.caption_text or "").replace("\n", " ")
        mtype = "Video/Reel" if m.media_type == 2 else ("Carousel" if m.media_type == 8 else "Photo")
        views = getattr(m, "view_count", 0) or getattr(m, "play_count", 0) or 0
        likes = getattr(m, "like_count", 0) or 0
        vurl = str(m.video_url) if hasattr(m, "video_url") and m.video_url else None
        
        data.append({
            "index": idx,
            "code": m.code,
            "id": str(m.id),
            "type": mtype,
            "views": views,
            "likes": likes,
            "caption": cap,
            "video_url": vurl,
            "url": f"https://www.instagram.com/reel/{m.code}/" if m.media_type == 2 else f"https://www.instagram.com/p/{m.code}/"
        })
        
    with open("scratch/justnature46_posts.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully saved {len(data)} posts to scratch/justnature46_posts.json")
    
    # Sort by likes
    top_liked = sorted([d for d in data if d["type"] == "Video/Reel"], key=lambda x: x["likes"], reverse=True)[:10]
    print("\n--- TOP 10 MOST LIKED REELS ON @justnature46 ---")
    for r in top_liked:
        print(f"[{r['likes']} likes | {r['views']} views] {r['url']}")
        print(f"   Caption: {r['caption'][:120]}")
except Exception as e:
    import traceback
    traceback.print_exc()
