"""
Sentence-Level Subtitle Burner for Sitcom Shorts
================================================
Replaces rapid single-word flash captions with clean, readable sentence blocks.
Covers the old flashing text area with a modern semi-transparent subtitle badge.
"""

import sys
import subprocess
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC_VIDEO = Path(r"D:\Media\shorts\optimized\diepvo8265_02_part1_Sheldon stands up for Amy_20s.mp4")
OUT_VIDEO = Path(r"D:\Media\shorts\optimized\diepvo8265_02_part1_Sheldon_sentences_20s.mp4")
ARTIFACT_DIR = Path(r"C:\Users\VICTUS\.gemini\antigravity\brain\bf5840ea-6324-46df-aad6-d6e9b73c7abb")

# Sentence timing within the 20-second clip
SENTENCE_TIMINGS = [
    (0.0, 2.5, "Amy... Amy..."),
    (2.5, 5.0, "Angry Amy?"),
    (5.0, 6.0, "What?"),
    (6.0, 8.5, "I hope this gift will make things better."),
    (8.5, 10.8, "Star Trek DVDs? Why would I want this?"),
    (10.8, 12.7, "First of all, you're welcome!"),
    (12.7, 16.2, "Furthermore, not being familiar with Wil Wheaton..."),
    (16.2, 19.8, "You were being rude to a national treasure!")
]

def render_sentence_video(src_path: Path, out_path: Path):
    print(f"[RENDER] Reading source video: {src_path}")
    cap = cv2.VideoCapture(str(src_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"[RENDER] Specs: {width}x{height} @ {fps:.1f} fps ({total_frames} frames)")

    temp_video = src_path.parent / "temp_silent_sentences.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_video), fourcc, fps, (width, height))

    # Pre-render subtitle overlays for each sentence
    try:
        font = ImageFont.truetype("arialbd.ttf", 28)
    except:
        font = ImageFont.load_default()

    pre_rendered = {}
    for start_t, end_t, text in SENTENCE_TIMINGS:
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        box_w = max(text_w + 60, 440)
        box_x1 = (width - box_w) // 2
        box_x2 = (width + box_w) // 2
        box_y1 = 740
        box_y2 = 850

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Draw dark rounded badge covering the old flashing words completely
        draw.rounded_rectangle(
            [box_x1, box_y1, box_x2, box_y2],
            radius=18,
            fill=(14, 14, 18, 240),
            outline=(255, 255, 255, 80),
            width=2
        )

        text_x = (width - text_w) // 2
        text_y = (box_y1 + box_y2 - text_h) // 2 - 3

        # Shadow + crisp text
        draw.text((text_x + 2, text_y + 2), text, font=font, fill=(0, 0, 0, 220))
        draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))

        pre_rendered[text] = overlay

    frame_idx = 0
    print("[RENDER] Rendering frames with clean sentence overlays...")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_time = frame_idx / fps
        active_text = None
        for start_t, end_t, text in SENTENCE_TIMINGS:
            if start_t <= current_time < end_t:
                active_text = text
                break

        if active_text and active_text in pre_rendered:
            # Composite overlay
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            comp = Image.alpha_composite(pil_img.convert("RGBA"), pre_rendered[active_text])
            final_frame = cv2.cvtColor(np.array(comp.convert("RGB")), cv2.COLOR_RGB2BGR)
            writer.write(final_frame)
        else:
            writer.write(frame)

        frame_idx += 1

    cap.release()
    writer.release()
    print("[RENDER] Silent video render complete. Muxing original audio...")

    # Combine with original audio
    mux_cmd = [
        "ffmpeg", "-y",
        "-i", str(temp_video),
        "-i", str(src_path),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(out_path)
    ]
    subprocess.run(mux_cmd, capture_output=True, check=True)
    if temp_video.exists():
        temp_video.unlink()

    print(f"[SUCCESS] Sentence-subtitled video created: {out_path} ({out_path.stat().st_size / (1024*1024):.2f} MB)")

    # Copy to artifact dir for instant playback / review
    dst_art = ARTIFACT_DIR / "sample_sentences_short_20s.mp4"
    import shutil
    shutil.copy2(out_path, dst_art)
    print(f"📋 Copied to artifact directory: {dst_art}")

if __name__ == "__main__":
    render_sentence_video(SRC_VIDEO, OUT_VIDEO)
