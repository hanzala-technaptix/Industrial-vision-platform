from pathlib import Path
import torch


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent


def _first_existing(paths):
    for p in paths:
        if p is not None and Path(p).exists():
            return Path(p)
    return None


_MASK_WEIGHTS_CANDIDATES = [
    REPO_ROOT / "models" / "yolo" / "mask_yolov8_best.pt",
]
_FALLBACK_WEIGHTS_CANDIDATES = [
    REPO_ROOT / "models" / "yolo" / "yolov8n.pt",
]

_resolved_mask = _first_existing(_MASK_WEIGHTS_CANDIDATES)
YOLO_MODEL_PATH = _resolved_mask or _MASK_WEIGHTS_CANDIDATES[0]
_resolved_fallback = _first_existing(_FALLBACK_WEIGHTS_CANDIDATES)
YOLO_FALLBACK_MODEL_PATH = _resolved_fallback or _FALLBACK_WEIGHTS_CANDIDATES[0]

BASE_DIR = REPO_ROOT
MODEL_DIR = REPO_ROOT / "models"
DATA_DIR = REPO_ROOT / "data"
LOG_DIR = REPO_ROOT / "logs"


VIDEO_SOURCE = 0
TARGET_FPS = 15

# 0.15–0.25 recommended for small / low-res webcam frames
CONF_THRESHOLD = 0.18
IOU_THRESHOLD = 0.3
INFER_IMGSZ = 640

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
LOG_LEVEL = "INFO"

# Throttled stdout: raw box counts, class filter drop hints, model.names at load
YOLO_DEBUG = True
YOLO_DEBUG_EVERY_N_FRAMES = 20

ENABLE_TRACKING = True
ENABLE_FACE_RECOGNITION = True

# API Configuration
API_BASE_URL = "http://localhost:8001"
API_EVENTS_ENDPOINT = f"{API_BASE_URL}/events"
API_TIMEOUT = 0.5  # seconds

# Event Building Configuration
PERSON_CONFIDENCE = 0.4  # Min confidence for person detection
CAMERA_ID = "CAM_01"  # Camera identifier
EVENT_COOLDOWN = 2.0  # Cooldown between events per object (seconds)
EVENT_TYPES = {
    "no_mask_detected": "no_mask",
    "person_detected": "person",
    "mask_detected": "mask",
}
