import sys
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import csv
import subprocess
import yt_dlp
from datetime import datetime

OUTPUT_DIR = r"D:\Media\shorts\just_nature\norway"
TEMP_DIR = r"D:\Media\shorts\just_nature\norway\temp_download"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Curated 30 Shorts for November (Nov 1 - Nov 30)
# Strictly adhering to the @justnature46 viral aesthetic
NORWAY_SHORTS = [
    {
        "index": 1,
        "date": "2026-11-01T18:00:00Z",
        "id": "E511UL2X1VI",
        "slug": "flamsbana_most_scenic_fjord_train",
        "title": "The Flåm Railway: Norway's Most Dramatic Fjord Train Ride 🚆🇳🇴",
        "location": "The Flåm Railway (Flåmsbana), Aurland, Norway",
        "pillar": "Scenic Fjord Trains",
        "hook": "Descending 866 meters from mountain glaciers straight into the deep emerald fjord."
    },
    {
        "index": 2,
        "date": "2026-11-02T18:00:00Z",
        "id": "Aof7LSK6VDo",
        "slug": "voringsfossen_roaring_canyon_waterfall",
        "title": "Vøringsfossen: Norway's Most Thunderous Canyon Waterfall 🌊🏔️",
        "location": "Vøringsfossen, Eidfjord, Norway",
        "pillar": "Roaring Waterfalls",
        "hook": "182 meters of pure roaring glacial power crashing into the dramatic Måbødalen canyon."
    },
    {
        "index": 3,
        "date": "2026-11-03T18:00:00Z",
        "id": "ZTWRSKmlg74",
        "slug": "reine_lofoten_aurora_timelapse",
        "title": "Magical Aurora Borealis Over Reine, Lofoten Islands 🌌✨",
        "location": "Reine, Lofoten Islands, Norway",
        "pillar": "Northern Lights & Arctic Peaks",
        "hook": "The night sky dancing in vivid neon green over traditional red arctic cabins."
    },
    {
        "index": 4,
        "date": "2026-11-04T18:00:00Z",
        "id": "rcJbn6qlv60",
        "slug": "stegastein_floating_above_fjords",
        "title": "Stegastein: Floating 650 Meters Above the Norwegian Fjords ☁️🇳🇴",
        "location": "Stegastein Viewpoint, Aurlandsfjord, Norway",
        "pillar": "Dramatic Cliffs & Viewpoints",
        "hook": "Stepping out onto a glass platform suspended high above the tranquil emerald fjord."
    },
    {
        "index": 5,
        "date": "2026-11-05T18:00:00Z",
        "id": "QyDr9mvi4hs",
        "slug": "naeroyfjord_unesco_narrow_fjord",
        "title": "Nærøyfjord: The Narrowest UNESCO Fjord on Earth 🚤🏔️",
        "location": "Nærøyfjord, Vestland, Norway",
        "pillar": "Fjord Wonders",
        "hook": "Towering vertical mountain walls only 250 meters apart rising straight from glacial waters."
    },
    {
        "index": 6,
        "date": "2026-11-06T18:00:00Z",
        "id": "cBbOa3p7U3s",
        "slug": "latefossen_twin_waterfall_odda",
        "title": "Låtefossen: The Famous Twin Waterfalls of Norway 🌊🇨🇭",
        "location": "Låtefossen, Odda, Norway",
        "pillar": "Roaring Waterfalls",
        "hook": "Two mighty torrents joining together right beneath an ancient stone arch bridge."
    },
    {
        "index": 7,
        "date": "2026-11-07T18:00:00Z",
        "id": "313Lv3gKPe0",
        "slug": "reine_fairytale_arctic_village",
        "title": "Reine: The Most Beautiful Fairytale Village in Norway 🏡🏔️",
        "location": "Reine, Lofoten Islands, Norway",
        "pillar": "Arctic Peaks & Fjords",
        "hook": "Red fishermen's cabins nestled beneath razor-sharp granite peaks in the Arctic."
    },
    {
        "index": 8,
        "date": "2026-11-08T18:00:00Z",
        "id": "U2em3cPHr88",
        "slug": "kjeragbolten_giant_boulder_cliff",
        "title": "Kjeragbolten: Standing on a Boulder Suspended in Mid-Air 😱🪨",
        "location": "Kjerag, Rogaland, Norway",
        "pillar": "Dramatic Cliffs & Viewpoints",
        "hook": "A 5-cubic-meter giant glacial rock wedged tightly between two 1,000-meter cliffs."
    },
    {
        "index": 9,
        "date": "2026-11-09T18:00:00Z",
        "id": "frgt8_jkG-g",
        "slug": "sommaroy_midnight_sun_paradise",
        "title": "Sommarøy: The Arctic Island Where Time Stands Still 🏝️🌅",
        "location": "Sommarøy, Tromsø, Norway",
        "pillar": "Arctic Paradise",
        "hook": "Crystal clear turquoise shallow waters and golden midnight sun in northern Norway."
    },
    {
        "index": 10,
        "date": "2026-11-10T18:00:00Z",
        "id": "YRY5uOm8jP4",
        "slug": "hardangerfjord_kingdom_of_waterfalls",
        "title": "Hardangerfjord: The Kingdom of Waterfalls & Orchards 🍎🌊",
        "location": "Hardangerfjord, Norway",
        "pillar": "Fjord Wonders",
        "hook": "Gliding across Norway's second-longest fjord surrounded by blooming fruit trees and falls."
    },
    {
        "index": 11,
        "date": "2026-11-11T18:00:00Z",
        "id": "rEmL8hmqVBQ",
        "slug": "sakrisoy_yellow_cabins_emerald_sea",
        "title": "Sakrisøy: Iconic Yellow Cabins on Emerald Arctic Waters 💛🌊",
        "location": "Sakrisøy, Lofoten, Norway",
        "pillar": "Arctic Peaks & Fjords",
        "hook": "The bright yellow seaside rorbuer glowing under the Arctic midnight sun."
    },
    {
        "index": 12,
        "date": "2026-11-12T18:00:00Z",
        "id": "mSU1t3PFcjo",
        "slug": "seven_sisters_waterfall_geirangerfjord",
        "title": "Seven Sisters Waterfall: Cascading into Geirangerfjord 🌊👑",
        "location": "Geirangerfjord, UNESCO, Norway",
        "pillar": "Roaring Waterfalls",
        "hook": "Seven distinct glacial streams tumbling 250 meters directly into the deep blue fjord."
    },
    {
        "index": 13,
        "date": "2026-11-13T18:00:00Z",
        "id": "7MDLTBhNPwU",
        "slug": "preikestolen_pulpit_rock_drone",
        "title": "Preikestolen: The 604-Meter Sheer Drop of Pulpit Rock 🦅⛰️",
        "location": "Preikestolen, Lysefjord, Norway",
        "pillar": "Dramatic Cliffs & Viewpoints",
        "hook": "Looking straight down a vertical flat cliff into the depths of Lysefjord."
    },
    {
        "index": 14,
        "date": "2026-11-14T18:00:00Z",
        "id": "uJld-U0rnys",
        "slug": "trollstigen_serpentine_mountain_road",
        "title": "Trollstigen: The Serpentine Troll Road of Norway 🐍🏔️",
        "location": "Trollstigen, Rauma, Norway",
        "pillar": "Mountain Passes",
        "hook": "11 hairpin bends carving through vertical mountain walls beside Stigfossen waterfall."
    },
    {
        "index": 15,
        "date": "2026-11-15T18:00:00Z",
        "id": "J46GIzz9dlA",
        "slug": "briksdalsbreen_blue_glacial_ice",
        "title": "Briksdalsbreen: Ancient Deep Blue Glacial Ice 🧊🏔️",
        "location": "Jostedalsbreen National Park, Norway",
        "pillar": "Glaciers & Ice",
        "hook": "An arm of Europe's largest mainland glacier plunging into a turquoise glacial lake."
    },
    {
        "index": 16,
        "date": "2026-11-16T18:00:00Z",
        "id": "GdfosXTCUnc",
        "slug": "flydalsjuvet_geirangerfjord_view",
        "title": "Flydalsjuvet: The Classic Postcard View of Geirangerfjord 📸🇳🇴",
        "location": "Flydalsjuvet, Geiranger, Norway",
        "pillar": "Fjord Wonders",
        "hook": "The ultimate vantage point looking down upon cruise ships dwarfed by gigantic fjords."
    },
    {
        "index": 17,
        "date": "2026-11-17T18:00:00Z",
        "id": "QfKfBhR3gnA",
        "slug": "hamnoy_iconic_bridge_view",
        "title": "Hamnøy: The Most Photographed Spot in the Arctic Circle 📸❄️",
        "location": "Hamnøy, Lofoten, Norway",
        "pillar": "Arctic Peaks & Fjords",
        "hook": "Wooden red stilts above black arctic seas framed by the colossal Mount Olstind."
    },
    {
        "index": 18,
        "date": "2026-11-18T18:00:00Z",
        "id": "ZtCHFCpNCeU",
        "slug": "tromso_sailing_under_aurora",
        "title": "Sailing Under the Dancing Northern Lights in Tromsø ⛵💚",
        "location": "Tromsø, Arctic Norway",
        "pillar": "Northern Lights & Arctic Peaks",
        "hook": "Silent electric boat gliding through arctic waters under an emerald auroral storm."
    },
    {
        "index": 19,
        "date": "2026-11-19T18:00:00Z",
        "id": "DNesRHobdPo",
        "slug": "flam_railway_window_view",
        "title": "Flåmsbana: Looking Out The Window of Norway's Greatest Journey 🚆🏞️",
        "location": "The Flåm Railway, Norway",
        "pillar": "Scenic Fjord Trains",
        "hook": "Wild waterfalls and mountain farms whizzing past your panoramic train window."
    },
    {
        "index": 20,
        "date": "2026-11-20T18:00:00Z",
        "id": "YXowxEdPP8I",
        "slug": "reinebringen_stairway_to_heaven",
        "title": "Reinebringen: Norway's Stairway to Heaven Viewpoint 🧗‍♂️✨",
        "location": "Reinebringen, Lofoten, Norway",
        "pillar": "Dramatic Cliffs & Viewpoints",
        "hook": "1,560 stone Sherpa stairs leading to the most breathtaking panoramic ridge on earth."
    },
    {
        "index": 21,
        "date": "2026-11-21T18:00:00Z",
        "id": "7u_XQE_FeOM",
        "slug": "alesund_aksla_art_nouveau_city",
        "title": "Ålesund: Norway's Fairytale Art Nouveau City By The Sea 🏰🌊",
        "location": "Aksla Viewpoint, Ålesund, Norway",
        "pillar": "Fairytale Coastal Towns",
        "hook": "418 steps up Mount Aksla overlooking islands, peninsulas, and open ocean."
    },
    {
        "index": 22,
        "date": "2026-11-22T18:00:00Z",
        "id": "6-tcy4O66RA",
        "slug": "lofoten_drone_4k_cinematic",
        "title": "Lofoten Islands: Where Jagged Mountains Rise from the Sea 🦅🌊",
        "location": "Lofoten Archipelago, Norway",
        "pillar": "Arctic Peaks & Fjords",
        "hook": "Untamed wilderness untouched by time above the Arctic Circle."
    },
    {
        "index": 23,
        "date": "2026-11-23T18:00:00Z",
        "id": "wfY_56rq6RQ",
        "slug": "hjorundfjord_sunnmore_alps",
        "title": "Hjørundfjord: Hidden Gem of the Sunnmøre Alps 🏔️💎",
        "location": "Hjørundfjorden, Møre og Romsdal, Norway",
        "pillar": "Fjord Wonders",
        "hook": "A pristine alpine fjord surrounded by 1,700-meter jagged summits."
    },
    {
        "index": 24,
        "date": "2026-11-24T18:00:00Z",
        "id": "MseDPZAY7U0",
        "slug": "voringsfossen_frozen_winter_wonder",
        "title": "Vøringsfossen in Winter: The Frozen Giant of Norway ❄️🧊",
        "location": "Vøringsfossen, Hardangervidda, Norway",
        "pillar": "Roaring Waterfalls",
        "hook": "Giant ice columns and frozen mist turning the waterfall into a crystalline palace."
    },
    {
        "index": 25,
        "date": "2026-11-25T18:00:00Z",
        "id": "I81Aul7Po2w",
        "slug": "sommaroy_aurora_beach_night",
        "title": "Sommarøy: Watching the Northern Lights From White Coral Beaches 🌌🏖️",
        "location": "Sommarøy, Troms, Norway",
        "pillar": "Northern Lights & Arctic Peaks",
        "hook": "Emerald light curtains reflecting across white arctic sand beaches."
    },
    {
        "index": 26,
        "date": "2026-11-26T18:00:00Z",
        "id": "_BD5znyffxM",
        "slug": "pulpit_rock_standing_on_the_edge",
        "title": "Preikestolen: Walking to the Edge of Pulpit Rock 🚶‍♂️⛰️",
        "location": "Preikestolen, Norway",
        "pillar": "Dramatic Cliffs & Viewpoints",
        "hook": "No guard rails, just pure raw nature 600 meters above the Lysefjord."
    },
    {
        "index": 27,
        "date": "2026-11-27T18:00:00Z",
        "id": "ikDUp-K4lwU",
        "slug": "flam_railway_as_seen_by_a_troll",
        "title": "Flåmsbana: Norway's Engineering Masterpiece in 4K 🚂🌲",
        "location": "Flåm Railway, Vestland, Norway",
        "pillar": "Scenic Fjord Trains",
        "hook": "One of the steepest standard-gauge railway lines in the world with zero rack-rail."
    },
    {
        "index": 28,
        "date": "2026-11-28T18:00:00Z",
        "id": "tvledy3dbUs",
        "slug": "hardangerfjord_scenic_cruise",
        "title": "Hardangerfjord Cruise: Pure Serenity on Norway's Waters 🚢💧",
        "location": "Hardangerfjord, Norway",
        "pillar": "Fjord Wonders",
        "hook": "Calm mirror waters reflecting endless rows of orchards and glacier-fed peaks."
    },
    {
        "index": 29,
        "date": "2026-11-29T18:00:00Z",
        "id": "6yGgcSdJ0eM",
        "slug": "latefossen_mist_bridge_view",
        "title": "Låtefossen: The Power of Twin Glacial Torrents 🌊💨",
        "location": "Låtefossen, Odda, Norway",
        "pillar": "Roaring Waterfalls",
        "hook": "The thundering spray that drenches travelers crossing the stone highway bridge."
    },
    {
        "index": 30,
        "date": "2026-11-30T18:00:00Z",
        "id": "Bx8x_YOkxfQ",
        "slug": "tromso_fjellet_aurora_timelapse",
        "title": "Tromsø: The Grand Aurora Finale from Mountain Fjellheisen 🌌👑",
        "location": "Fjellheisen, Tromsø, Norway",
        "pillar": "Northern Lights & Arctic Peaks",
        "hook": "Standing atop Mount Storsteinen as the sky explodes into waves of purple and emerald green."
    }
]

def build_description(item):
    return (
        f"{item['title']}\n\n"
        f"{item['hook']}\n\n"
        f"📍 Location: {item['location']}\n"
        f"🏔️ Category: {item['pillar']}\n\n"
        f"Welcome to Just Nature (@Just.Nature46)! We bring you the most breathtaking landscapes, "
        f"scenic fjord journeys, and peaceful nature views from Norway, Switzerland, and around the world.\n\n"
        f"✨ Subscribe to @Just.Nature46 for daily wanderlust & nature relaxation!\n"
        f"❤️ Like, save, and share this with someone who needs to see this view!\n\n"
        f"#norway #nature #travel #fjords #shorts #flam #geiranger #lofoten #aurora #waterfall "
        f"#wanderlust #landscape #4knature #preikestolen #norwegianfjords"
    )

TAGS = [
    "norway", "norwaytravel", "nature", "travel", "shorts", "viralshorts",
    "wanderlust", "fjords", "norwegianfjords", "flamsbana", "geirangerfjord",
    "lofoten", "northernlights", "aurora", "waterfalls", "landscape", "4knature",
    "preikestolen", "trolltunga", "visitnorway"
]

def main():
    print("=== Processing 30 Curated Shorts for Norway (Nov 1 - Nov 30) ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    ydl_opts_base = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
    }
    
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    queue_path = os.path.join(OUTPUT_DIR, "upload_queue.json")
    csv_path = os.path.join(OUTPUT_DIR, "schedule.csv")
    
    manifest = []
    upload_queue = []
    csv_rows = [["Scheduled Time (ISO)", "Filename", "Title", "Description", "Tags"]]
    
    for idx, v in enumerate(NORWAY_SHORTS, 1):
        vid_id = v["id"]
        slug = f"just_nature_norway_{idx:02d}_{v['slug']}"
        raw_download_path = os.path.join(TEMP_DIR, f"{slug}_raw.mp4")
        final_video_path = os.path.join(OUTPUT_DIR, f"{slug}.mp4")
        thumb_path = os.path.join(OUTPUT_DIR, f"{slug}_thumb.jpg")
        
        print(f"\n[{idx:02d}/30] Processing: {v['title']}")
        
        # 1. Download source if needed
        if not os.path.exists(final_video_path):
            if not os.path.exists(raw_download_path):
                print(f"  -> Downloading {v['id']}...")
                ydl_opts = dict(ydl_opts_base)
                ydl_opts["outtmpl"] = raw_download_path
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.extract_info(f"https://www.youtube.com/shorts/{vid_id}", download=True)
                except Exception as e:
                    print(f"  [!] Fallback downloading watch url: {e}")
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.extract_info(f"https://www.youtube.com/watch?v={vid_id}", download=True)
            
            # 2. Check dimensions via ffprobe
            probe_cmd = [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0",
                raw_download_path
            ]
            probe_res = subprocess.run(probe_cmd, capture_output=True, text=True).stdout.strip().split(",")
            w = int(probe_res[0])
            h = int(probe_res[1])
            print(f"  -> Raw dimensions: {w}x{h}")
            
            # 3. Format into pristine 1080x1920 vertical video
            if h >= w:
                vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
            else:
                vf = "scale=-1:1920,crop=1080:1920"
                
            print(f"  -> Formatting to vertical 1080x1920...")
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", raw_download_path,
                "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                "-x264-params", "rc-lookahead=10:b-adapt=0:threads=2",
                final_video_path
            ]
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            try:
                os.remove(raw_download_path)
            except Exception:
                pass
        else:
            print(f"  -> Final video already exists at {final_video_path}")
            
        # 4. Generate high-res cover thumbnail
        if not os.path.exists(thumb_path):
            thumb_cmd = [
                "ffmpeg", "-y", "-ss", "00:00:03", "-i", final_video_path,
                "-vframes", "1", "-q:v", "2", thumb_path
            ]
            subprocess.run(thumb_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  -> Generated thumbnail: {thumb_path}")
            
        desc = build_description(v)
        
        # Build queue & manifest item
        entry = {
            "index": idx,
            "filename": f"{slug}.mp4",
            "filepath": final_video_path,
            "thumbnail": thumb_path,
            "title": v["title"],
            "pillar": v["pillar"],
            "location": v["location"],
            "hook": v["hook"],
            "description": desc,
            "tags": TAGS,
            "scheduled_time": v["date"],
            "source_id": vid_id,
            "source_url": f"https://www.youtube.com/shorts/{vid_id}"
        }
        
        manifest.append(entry)
        upload_queue.append(entry)
        csv_rows.append([
            v["date"],
            f"{slug}.mp4",
            v["title"],
            desc,
            ", ".join(TAGS)
        ])

    # Save manifest.json
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        
    # Save upload_queue.json
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(upload_queue, f, indent=2, ensure_ascii=False)
        
    # Save schedule.csv
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(csv_rows)
        
    print(f"\n[DONE] Successfully processed all 30 Norway shorts for November!")
    print(f"Manifest: {manifest_path}")
    print(f"Upload Queue: {queue_path}")
    print(f"Schedule CSV: {csv_path}")

if __name__ == "__main__":
    main()
