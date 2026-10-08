"""
Boxless Lowered Sentence-Level Subtitle Burner
==============================================
1. Places new sentence subtitles lower on screen (y = 920) for optimal mobile viewing.
2. Completely removes / inpaints all underlying old single-word subtitles on every frame.
3. Renders clean text with thick black outline and drop shadow (no background box).
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

SUBTITLE_Y = 920  # Lowered position

def render_boxless_video(src_path: Path, out_path: Path, text_color=(255, 255, 255)):
    print(f"[RENDER] Processing video: {src_path}")
    cap = cv2.VideoCapture(str(src_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    temp_video = src_path.parent / "temp_silent_lower.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_video), fourcc, fps, (width, height))

    try:
        font = ImageFont.truetype("arialbd.ttf", 31)
    except:
        font = ImageFont.load_default()

    # Pre-render text overlays at lowered Y position (NO BOX)
    pre_rendered = {}
    for start_t, end_t, text in SENTENCE_TIMINGS:
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        x = (width - text_w) // 2
        y = SUBTITLE_Y

        # Drop shadow + thick black outline (stroke) - NO BOX
        draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 220))
        draw.text((x, y), text, font=font, fill=text_color, stroke_width=4, stroke_fill=(0, 0, 0, 255))

        pre_rendered[text] = overlay

    roi_y1, roi_y2 = 740, 870
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))

    frame_idx = 0
    print("[RENDER] Applying continuous inpaint on old text & burning lowered sentences...")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Inpaint old flashing single words on EVERY frame in the old subtitle zone
        roi = frame[roi_y1:roi_y2, :]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        mask = (gray > 195).astype(np.uint8) * 255
        if np.any(mask):
            mask_dil = cv2.dilate(mask, kernel, iterations=1)
            full_mask = np.zeros((height, width), dtype=np.uint8)
            full_mask[roi_y1:roi_y2, :] = mask_dil
            frame = cv2.inpaint(frame, full_mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)

        current_time = frame_idx / fps
        active_text = None
        for start_t, end_t, text in SENTENCE_TIMINGS:
            if start_t <= current_time < end_t:
                active_text = text
                break

        if active_text and active_text in pre_rendered:
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
    print("[RENDER] Frame processing complete. Muxing audio...")

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

    print(f"[SUCCESS] Clean lowered sentence video created: {out_path} ({out_path.stat().st_size / (1024*1024):.2f} MB)")

    # Copy to artifact dir
    dst_art = ARTIFACT_DIR / "sample_sentences_short_20s.mp4"
    import shutil
    shutil.copy2(out_path, dst_art)
    print(f"[COPIED] Artifact updated: {dst_art}")

if __name__ == "__main__":
    render_boxless_video(SRC_VIDEO, OUT_VIDEO)
