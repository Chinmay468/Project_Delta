"""
Intelligent Face-Centered Vertical 9:16 Video Cropping.

Uses MediaPipe and OpenCV Haar Cascade face detection with Exponential
Moving Average (EMA) smoothing to reframe 16:9/2.35:1 widescreen footage
into smooth 9:16 vertical video (1080x1920) focused on the speaker.
"""

import argparse
import os
import subprocess
import sys
import cv2
import numpy as np

# ── Tool resolver ────────────────────────────────────────────────────────────

try:
    from build_video import _find_tool
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from build_video import _find_tool


# ── Face Detector Hierarchy with Automated Fallback ───────────────────────────

_DETECTOR_CACHE = None


def _init_mediapipe_detector():
    """Attempt to initialize MediaPipe face detection."""
    try:
        import mediapipe as mp
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
            detector = mp.solutions.face_detection.FaceDetection(
                model_selection=1,
                min_detection_confidence=0.5,
            )
            return detector
    except Exception:
        pass
    return None


def _init_opencv_dnn_detector():
    """Attempt to initialize OpenCV DNN Face Detector (YuNet)."""
    try:
        if not hasattr(cv2, "FaceDetectorYN"):
            return None
        models_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "assets", "models")
        )
        model_path = os.path.join(models_dir, "face_detection_yunet_2023mar.onnx")
        if not os.path.isfile(model_path):
            import urllib.request
            os.makedirs(models_dir, exist_ok=True)
            url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
            urllib.request.urlretrieve(url, model_path)

        if os.path.isfile(model_path):
            detector = cv2.FaceDetectorYN.create(model_path, "", (320, 320), score_threshold=0.5)
            return detector
    except Exception:
        pass
    return None


def _init_haar_cascade_detector():
    """Load Haar Cascade classifier from cv2.data.haarcascades or local fallback."""
    try:
        candidate = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        if os.path.isfile(candidate):
            cascade = cv2.CascadeClassifier(candidate)
            if not cascade.empty():
                return cascade
    except Exception:
        pass

    local_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "assets", "models", "haarcascade_frontalface_default.xml")
    )
    if os.path.isfile(local_path):
        cascade = cv2.CascadeClassifier(local_path)
        if not cascade.empty():
            return cascade

    return None


def get_face_detector():
    """
    Model Loader & Fallback Hierarchy:
    1. Check assets/models/face_detection_yunet_2023mar.onnx via cv2.FaceDetectorYN (fast, modern, accurate)
    2. Fall back to assets/models/haarcascade_frontalface_default.xml via cv2.CascadeClassifier
    3. Fall back to MediaPipe if available
    4. If no face is detected in a frame, fall back to dead-center framing (0.5).
    """
    global _DETECTOR_CACHE
    if _DETECTOR_CACHE is not None:
        return _DETECTOR_CACHE

    # 1. Primary: YuNet ONNX Face Detector
    dnn_det = _init_opencv_dnn_detector()
    if dnn_det is not None:
        print("[face_crop] Using OpenCV DNN Face Detector (YuNet ONNX).")
        _DETECTOR_CACHE = ("opencv_dnn", dnn_det)
        return _DETECTOR_CACHE

    # 2. Fallback: Haar Cascade Classifier
    cascade_det = _init_haar_cascade_detector()
    if cascade_det is not None:
        print("[face_crop] YuNet unavailable. Using OpenCV Haar Cascade Classifier (haarcascade_frontalface_default.xml).")
        _DETECTOR_CACHE = ("haar_cascade", cascade_det)
        return _DETECTOR_CACHE

    # 3. Fallback: MediaPipe Face Detection
    mp_det = _init_mediapipe_detector()
    if mp_det is not None:
        print("[face_crop] Using MediaPipe FaceDetection.")
        _DETECTOR_CACHE = ("mediapipe", mp_det)
        return _DETECTOR_CACHE

    print("[face_crop] WARNING: No local face models loaded; defaulting to dead-center framing (0.5).")
    _DETECTOR_CACHE = ("none", None)
    return _DETECTOR_CACHE


def _detect_mediapipe(frame: np.ndarray, detector) -> float:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = detector.process(rgb)
    if results and results.detections:
        best_box = None
        max_area = -1.0
        for det in results.detections:
            bb = det.location_data.relative_bounding_box
            area = bb.width * bb.height
            if area > max_area:
                max_area = area
                best_box = bb
        if best_box:
            center_x = best_box.xmin + (best_box.width / 2.0)
            return float(np.clip(center_x, 0.0, 1.0))
    return None


def _detect_opencv_dnn(frame: np.ndarray, detector) -> float:
    h, w = frame.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(frame)
    if faces is not None and len(faces) > 0:
        best_face = max(faces, key=lambda f: f[2] * f[3])
        fx, fy, fw, fh = best_face[:4]
        center_x = (fx + fw / 2.0) / float(w)
        return float(np.clip(center_x, 0.0, 1.0))
    return None


def _detect_haar_cascade(frame: np.ndarray, detector) -> float:
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = detector.detectMultiScale(
        gray,
        scaleFactor=1.15,
        minNeighbors=4,
        minSize=(int(h * 0.08), int(h * 0.08)),
    )
    if len(faces) > 0:
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        fx, fy, fw, fh = largest_face
        center_x = (fx + fw / 2.0) / float(w)
        return float(np.clip(center_x, 0.0, 1.0))
    return None


def detect_face_center_x(frame: np.ndarray, detector_info=None) -> float:
    """
    Detect primary face in frame and return normalized X coordinate (0.0 to 1.0).
    Returns 0.5 if no face detected.
    """
    if detector_info is None:
        det_type, detector = get_face_detector()
    else:
        det_type, detector = detector_info

    if detector is None or det_type == "none":
        return 0.5

    result = None
    if det_type == "mediapipe":
        result = _detect_mediapipe(frame, detector)
    elif det_type == "opencv_dnn":
        result = _detect_opencv_dnn(frame, detector)
    elif det_type == "haar_cascade":
        result = _detect_haar_cascade(frame, detector)

    if result is not None:
        return result
    return 0.5


# ── Video Saliency & Focal Analysis ───────────────────────────────────────────

def analyze_focal_center_x(
    video_path: str,
    start_sec: float,
    duration_sec: float,
    sample_interval: float = 0.3,
    sample_fps: float = None,
) -> float:
    """
    Sample frames every 0.3s across the cut interval and smooth the horizontal
    center coordinate (X) using an Exponential Moving Average (alpha = 0.2).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video file: '{video_path}'")

    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    start_frame = int(start_sec * fps)
    end_frame = min(int((start_sec + duration_sec) * fps), total_frames)
    if sample_fps is not None and sample_fps > 0:
        frame_step = max(int(fps / sample_fps), 1)
    else:
        frame_step = max(int(fps * sample_interval), 1)

    detector_info = get_face_detector()

    focal_points = []
    current_smoothed_x = 0.5
    alpha = 0.2  # Exponential Moving Average factor (alpha = 0.2)

    for f_idx in range(start_frame, end_frame, frame_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if not ret:
            break

        detected_x = detect_face_center_x(frame, detector_info=detector_info)

        # Smooth using EMA (alpha = 0.2)
        current_smoothed_x = (alpha * detected_x) + ((1.0 - alpha) * current_smoothed_x)
        focal_points.append(current_smoothed_x)

    cap.release()

    if not focal_points:
        return 0.5

    # Return median smoothed focal center to reject extreme outliers
    return float(np.median(focal_points))


# ── Auto-Crop Execution via FFmpeg ────────────────────────────────────────────

def auto_crop_clip(
    video_path: str,
    start: float,
    duration: float,
    out_path: str,
    sample_interval: float = 0.3,
    sample_fps: float = None,
) -> str:
    """
    Extract a clip and crop into 9:16 vertical (1080x1920) centered on speaker.
    """
    cap = cv2.VideoCapture(video_path)
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if src_w <= 0 or src_h <= 0:
        raise ValueError(f"Could not retrieve dimensions of video: '{video_path}'")

    # Target 9:16 width inside input height
    crop_w = int(src_h * (9.0 / 16.0))
    if crop_w > src_w:
        crop_w = src_w

    # Detect optimal focal center X
    print(f"Analyzing focal center for {duration}s clip starting at {start}s...")
    focal_x = analyze_focal_center_x(
        video_path,
        start,
        duration,
        sample_interval=sample_interval,
        sample_fps=sample_fps,
    )

    # Compute crop left coordinate
    crop_x = int((focal_x * src_w) - (crop_w / 2.0))
    crop_x = max(0, min(crop_x, src_w - crop_w))

    print(f"Calculated 9:16 crop: {crop_w}x{src_h} at X={crop_x} (Focal center: {focal_x:.2f})")

    out_abs = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)

    ffmpeg_bin = _find_tool("ffmpeg")

    vf = f"crop=ih*(9/16):ih:{crop_x}:0,scale=1080:1920"

    cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", os.path.abspath(video_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        out_abs,
    ]

    subprocess.run(cmd, check=True, capture_output=True)
    print(f"Saved face-centered vertical clip to: {out_abs}")
    return out_abs


def main():
    parser = argparse.ArgumentParser(
        description="Face-tracking auto-cropper for 9:16 vertical Shorts."
    )
    parser.add_argument("video", help="Path to source video file")
    parser.add_argument("-s", "--start", type=float, required=True, help="Start timestamp in seconds")
    parser.add_argument("-t", "--duration", type=float, help="Duration in seconds")
    parser.add_argument("-e", "--end", type=float, help="End timestamp in seconds")
    parser.add_argument("-o", "--output", help="Output destination path (.mp4)")
    parser.add_argument("--interval", type=float, default=0.3, help="Sampling interval in seconds (default: 0.3s)")
    args = parser.parse_args()

    if args.duration is not None:
        duration = args.duration
    elif args.end is not None:
        duration = args.end - args.start
    else:
        duration = 30.0

    if duration <= 0:
        print(f"ERROR: Invalid duration ({duration}s). End must be greater than start.", file=sys.stderr)
        sys.exit(1)

    out_path = args.output
    if not out_path:
        base_name = os.path.splitext(os.path.basename(args.video))[0]
        out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "clips"))
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{base_name}_clip_01.mp4")

    try:
        auto_crop_clip(
            args.video,
            start=args.start,
            duration=duration,
            out_path=out_path,
            sample_interval=args.interval,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
