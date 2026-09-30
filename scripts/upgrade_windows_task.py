"""
Upgrades Windows Task Scheduler for Daily Instagram Reels Uploader
- Enables StartWhenAvailable (catch up immediately when PC turns on if 19:30 was missed)
- Enables WakeToRun (wakes PC from sleep if supported)
- Disables battery restrictions (runs on battery as well as AC power)
"""
import sys
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
BATCH_FILE = CONFIG_DIR / "run_daily_instagram_upload.bat"
XML_FILE = CONFIG_DIR / "task_definition.xml"
TASK_NAME = "DailyInstagramReelsUpload"

def upgrade_task():
    # Make sure batch file calls --post-next
    python_exe = sys.executable
    script_path = Path(__file__).resolve().parent / "instagram_reels_uploader.py"

    batch_content = (
        "@echo off\n"
        f'"{python_exe}" "{script_path}" --post-next >> "D:\\Media\\shorts\\instagram_upload.log" 2>&1\n'
    )
    with open(BATCH_FILE, "w", encoding="utf-8") as f:
        f.write(batch_content)
    print(f"[OK] Verified batch file: {BATCH_FILE}")

    # Query current task XML
    res = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME, "/XML"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[INFO] Task '{TASK_NAME}' not found. Creating base task first...")
        create_res = subprocess.run([
            "schtasks", "/Create", "/F",
            "/TN", TASK_NAME,
            "/TR", f'"{BATCH_FILE}"',
            "/SC", "DAILY",
            "/ST", "19:30"
        ], capture_output=True, text=True)
        if create_res.returncode != 0:
            print(f"[ERROR] Could not create base task: {create_res.stderr}")
            return False
        res = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME, "/XML"], capture_output=True, text=True)

    ET.register_namespace('', 'http://schemas.microsoft.com/windows/2004/02/mit/task')
    ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
    root = ET.fromstring(res.stdout)

    settings = root.find('t:Settings', ns)
    if settings is not None:
        dsb = settings.find('t:DisallowStartIfOnBatteries', ns)
        if dsb is not None:
            dsb.text = 'false'
        sig = settings.find('t:StopIfGoingOnBatteries', ns)
        if sig is not None:
            sig.text = 'false'

        swa = settings.find('t:StartWhenAvailable', ns)
        if swa is None:
            swa = ET.SubElement(settings, '{http://schemas.microsoft.com/windows/2004/02/mit/task}StartWhenAvailable')
        swa.text = 'true'

        wtr = settings.find('t:WakeToRun', ns)
        if wtr is None:
            wtr = ET.SubElement(settings, '{http://schemas.microsoft.com/windows/2004/02/mit/task}WakeToRun')
        wtr.text = 'true'

    xml_out = ET.tostring(root, encoding='utf-16', xml_declaration=True)
    with open(XML_FILE, 'wb') as f:
        f.write(xml_out)

    print(f"[OK] Generated upgraded Task XML: {XML_FILE}")

    # Re-import task
    res2 = subprocess.run(
        ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(XML_FILE.resolve()), "/F"],
        capture_output=True,
        text=True
    )

    if res2.returncode == 0:
        print(f"\n[SUCCESS] Windows Scheduled Task '{TASK_NAME}' upgraded successfully!")
        print("  - Scheduled Time:     19:30 Daily")
        print("  - Catch-up Mode:      StartWhenAvailable=True (runs when laptop powers on if 19:30 missed)")
        print("  - Wake Support:       WakeToRun=True (wakes laptop from sleep)")
        print("  - Power Management:   Runs on battery and AC power without stopping")
        return True
    else:
        print(f"[ERROR] Failed to re-register task: {res2.stderr}")
        return False

if __name__ == "__main__":
    upgrade_task()
