import sys
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEALTH_FILE = ROOT / "data" / "wealth_shorts" / "wealth_shorts_queue.json"

ASSET_VAULT_MEGA = "https://mega.nz/folder/PkJCxZiK#Hifq4nNRbUKvVWOzTnNXIQ"

with open(WEALTH_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

# Items #1 to #10 are already scheduled on YouTube Studio through Oct 12
# Items #11 to #41 are pending
for item in data["queue"]:
    item["mega_folder"] = ASSET_VAULT_MEGA
    idx = item["index"]
    if idx <= 10:
        item["status"] = "scheduled"
    else:
        item["status"] = "pending"

data["mega_folder"] = ASSET_VAULT_MEGA
data["scheduled_items"] = sum(1 for i in data["queue"] if i.get("status") == "scheduled")
data["pending_items"] = sum(1 for i in data["queue"] if i.get("status") == "pending")

with open(WEALTH_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Updated {WEALTH_FILE}:")
print(f"  Mega Folder: {ASSET_VAULT_MEGA}")
print(f"  Scheduled items: {data['scheduled_items']}")
print(f"  Pending items: {data['pending_items']}")
