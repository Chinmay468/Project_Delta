import json
from pathlib import Path

p = Path("data/instagram_queue.json")
data = json.loads(p.read_text(encoding="utf-8"))

for item in data["queue"]:
    idx = item.get("queue_index")
    if idx == 3:
        item["youtube_title"] = "Angry Amy's Gift From Sheldon 😂 #Shorts"
        item["trim_start"] = 56.5
        item["trim_end"] = 76.5
        item["local_path"] = r"D:\Media\shorts\diepvo8265_reels\diepvo8265_02_part1_Sheldon stands up for Amy.mp4"
        print("Updated Item 3 in queue")
    elif idx == 4:
        item["youtube_title"] = "Drunk Sheldon Confronts Wil Wheaton 💀 #Shorts"
        item["trim_start"] = 41.0
        item["trim_end"] = 79.8
        item["local_path"] = r"D:\Media\shorts\diepvo8265_reels\diepvo8265_02_part2_Sheldon stands up for Amy.mp4"
        print("Updated Item 4 in queue")

p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Successfully saved queue update!")
