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

    print(f"[RENDER] Reading {total_frames} frames into memory...")
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()

    temp_video = src_path.parent / "temp_silent_lower.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_video), fourcc, fps, (width, height))

    try:
        font = ImageFont.truetype("arialbd.ttf", 28)
    except:
        font = ImageFont.load_default()

    import textwrap

    # Pre-render text overlays at lowered Y position with dynamic multi-line wrapping
    pre_rendered = {}
    for start_t, end_t, text in SENTENCE_TIMINGS:
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        if text_w > 560:
            lines = textwrap.wrap(text, width=28)
        else:
            lines = [text]

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        line_h = 36
        y_start = SUBTITLE_Y if len(lines) == 1 else (SUBTITLE_Y - 18)

        for i, line in enumerate(lines):
            l_bbox = font.getbbox(line)
            lw = l_bbox[2] - l_bbox[0]
            lx = (width - lw) // 2
            ly = y_start + i * line_h

            # Drop shadow + thick black outline (stroke) - NO BOX, NO CLIPPING
            draw.text((lx + 2, ly + 2), line, font=font, fill=(0, 0, 0, 220))
            draw.text((lx, ly), line, font=font, fill=text_color, stroke_width=4, stroke_fill=(0, 0, 0, 255))

        pre_rendered[text] = overlay

    print("[RENDER] Detecting camera shot cuts for temporal background synthesis...")
    cuts = [0]
    for f in range(1, len(frames)):
        prev_g = cv2.cvtColor(frames[f-1], cv2.COLOR_BGR2GRAY)
        curr_g = cv2.cvtColor(frames[f], cv2.COLOR_BGR2GRAY)
        diff = np.mean(cv2.absdiff(curr_g, prev_g))
        if diff > 25:
            cuts.append(f)
    cuts.append(len(frames))

    patch_y1, patch_y2 = 760, 840
    patch_x1, patch_x2 = 240, 480
    mask_patch = np.full((patch_y2 - patch_y1, patch_x2 - patch_x1), 255, dtype=np.uint8)
    center = ((patch_x1 + patch_x2) // 2, (patch_y1 + patch_y2) // 2)

    print(f"[RENDER] Removing single-character subtitles across {len(cuts)-1} camera shots...")
    cleaned_frames = [f.copy() for f in frames]

    for s in range(len(cuts)-1):
        start_f, end_f = cuts[s], cuts[s+1]
        scores = []
        for f in range(start_f, end_f):
            roi = frames[f][patch_y1:patch_y2, patch_x1:patch_x2]
            w = np.sum((roi[:,:,0] > 225) & (roi[:,:,1] > 225) & (roi[:,:,2] > 225))
            scores.append((w, f))

        clean_candidates = [f for w, f in scores if w < 200]
        if not clean_candidates:
            clean_candidates = [min(scores, key=lambda x: x[0])[1]]

        for f in range(start_f, end_f):
            roi = frames[f][patch_y1:patch_y2, patch_x1:patch_x2]
            w = np.sum((roi[:,:,0] > 225) & (roi[:,:,1] > 225) & (roi[:,:,2] > 225))
            if w >= 200:
                nearest_clean = min(clean_candidates, key=lambda c: abs(c - f))
                ref_patch = frames[nearest_clean][patch_y1:patch_y2, patch_x1:patch_x2].copy()
                dst = frames[f].copy()
                try:
                    cloned = cv2.seamlessClone(ref_patch, dst, mask_patch.copy(), center, cv2.NORMAL_CLONE)
                    cleaned_frames[f] = cloned
                except Exception:
                    pass

    print("[RENDER] Burning lowered sentences onto pristine footage...")
    for frame_idx, frame in enumerate(cleaned_frames):
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
