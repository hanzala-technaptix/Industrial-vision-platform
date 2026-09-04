"""Central configuration."""
from __future__ import annotations

import os
from pathlib import Path

try:
    import torch

    _HAS_CUDA = torch.cuda.is_available()
except Exception:
    _HAS_CUDA = False

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _env_float(k, d):
    try:
        return float(os.getenv(k, d))
    except (TypeError, ValueError):
        return d


def _env_int(k, d):
    try:
        return int(os.getenv(k, d))
    except (TypeError, ValueError):
        return d


APP_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = APP_ROOT.parent
MODEL_DIR = REPO_ROOT / "models"
DATA_DIR = REPO_ROOT / "data"
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Server
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = _env_int("API_PORT", 8001)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Compute
DEVICE = os.getenv("DEVICE", "cuda" if _HAS_CUDA else "cpu")

# Camera
_video_env = os.getenv("VIDEO_SOURCE", "0")
VIDEO_SOURCE = int(_video_env) if _video_env.isdigit() else _video_env
CAMERA_ID = os.getenv("CAMERA_ID", "CAM_01")

# Pipeline
FRAME_WIDTH = _env_int("FRAME_WIDTH", 640)
FRAME_HEIGHT = _env_int("FRAME_HEIGHT", 360)
FRAME_SKIP = _env_int("FRAME_SKIP", 2)
JPEG_QUALITY = _env_int("JPEG_QUALITY", 80)

# PPE
PPE_MODEL_PATH = MODEL_DIR / "yolo" / "ppe_yolov8_best.pt"
PPE_FALLBACK_PATH = MODEL_DIR / "yolo" / "yolov8n.pt"
PPE_CONF_THRESHOLD = _env_float("PPE_CONF_THRESHOLD", 0.18)
PPE_IOU_THRESHOLD = _env_float("PPE_IOU_THRESHOLD", 0.45)
PPE_INFER_IMGSZ = _env_int("PPE_INFER_IMGSZ", 640)
PERSON_MODEL_PATH = MODEL_DIR / "yolo" / "yolov8n.pt"
PERSON_CONF_THRESHOLD = _env_float("PERSON_CONF_THRESHOLD", 0.35)
PERSON_INFER_IMGSZ = _env_int("PERSON_INFER_IMGSZ", 640)
PPE_ASSOC_MIN_OVERLAP = _env_float("PPE_ASSOC_MIN_OVERLAP", 0.30)
MASK_ASSOC_MIN_OVERLAP = _env_float("MASK_ASSOC_MIN_OVERLAP", 0.15)
PPE_POSITIVE_MIN_CONF = _env_float("PPE_POSITIVE_MIN_CONF", 0.25)
MASK_MODEL_PATH = MODEL_DIR / "yolo" / "mask_yolov8_best.pt"
MASK_CONF_THRESHOLD = _env_float("MASK_CONF_THRESHOLD", 0.15)
MASK_INFER_IMGSZ = _env_int("MASK_INFER_IMGSZ", 640)
PPE_VIOLATION_COOLDOWN = _env_float("PPE_VIOLATION_COOLDOWN", 10.0)
PPE_VIOLATION_MIN_FRAMES = _env_int("PPE_VIOLATION_MIN_FRAMES", 3)
PPE_REQUIRED_ITEMS = os.getenv("PPE_REQUIRED_ITEMS", "hardhat,mask,vest,gloves").split(",")

ACTIVE_PPE_CLASSES = {
    "Hardhat", "NO-Hardhat", "Mask", "NO-Mask",
    "Safety Vest", "NO-Safety Vest", "Gloves", "NO-Gloves",
}

PPE_CLASS_MAP = {
    "Person": ("person", "person"),
    "Hardhat": ("hardhat", "positive"),
    "NO-Hardhat": ("hardhat", "negative"),
    "Mask": ("mask", "positive"),
    "NO-Mask": ("mask", "negative"),
    "Safety Vest": ("vest", "positive"),
    "NO-Safety Vest": ("vest", "negative"),
    "Gloves": ("gloves", "positive"),
    "NO-Gloves": ("gloves", "negative"),
}

# Tracking
TRACK_DISTANCE_THRESHOLD = _env_float("TRACK_DISTANCE_THRESHOLD", 100.0)
TRACK_STALE_TIMEOUT = _env_float("TRACK_STALE_TIMEOUT", 3.0)

# Database
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "factory.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
