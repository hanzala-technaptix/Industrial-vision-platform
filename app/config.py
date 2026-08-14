"""Central configuration. Reads env vars where relevant, falls back to defaults."""
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
    try: return float(os.getenv(k, d))
    except (TypeError, ValueError): return d

def _env_int(k, d):
    try: return int(os.getenv(k, d))
    except (TypeError, ValueError): return d

def _env_bool(k, d):
    v = os.getenv(k)
    if v is None: return d
    return v.strip().lower() in ("1", "true", "yes", "on")


APP_ROOT = Path(__file__).resolve().parent
REPO_ROOT = APP_ROOT.parent
MODEL_DIR = REPO_ROOT / "models"
DATA_DIR = REPO_ROOT / "data"
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# -------- Server --------
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = _env_int("API_PORT", 8001)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# -------- Compute --------
DEVICE = os.getenv("DEVICE", "cuda" if _HAS_CUDA else "cpu")

# -------- Camera --------
_video_env = os.getenv("VIDEO_SOURCE", "0")
VIDEO_SOURCE = int(_video_env) if _video_env.isdigit() else _video_env
CAMERA_ID = os.getenv("CAMERA_ID", "CAM_01")

# -------- Pipeline --------
FRAME_WIDTH = _env_int("FRAME_WIDTH", 640)
FRAME_HEIGHT = _env_int("FRAME_HEIGHT", 360)
FRAME_SKIP = _env_int("FRAME_SKIP", 2)
JPEG_QUALITY = _env_int("JPEG_QUALITY", 80)

# -------- PPE detector --------
PPE_MODEL_PATH = MODEL_DIR / "yolo" / "ppe_yolov8_best.pt"
PPE_FALLBACK_PATH = MODEL_DIR / "yolo" / "yolov8n.pt"
PPE_CONF_THRESHOLD = _env_float("PPE_CONF_THRESHOLD", 0.35)
PPE_IOU_THRESHOLD = _env_float("PPE_IOU_THRESHOLD", 0.45)
PPE_INFER_IMGSZ = _env_int("PPE_INFER_IMGSZ", 640)

# The PPE model's Person class is unreliable on real footage; we detect persons
# with COCO yolov8n.pt instead and reserve the PPE model for equipment only.
PERSON_MODEL_PATH = MODEL_DIR / "yolo" / "yolov8n.pt"
PERSON_CONF_THRESHOLD = _env_float("PERSON_CONF_THRESHOLD", 0.35)
PERSON_INFER_IMGSZ = _env_int("PERSON_INFER_IMGSZ", 640)
# Fraction of PPE bbox area that must overlap the person bbox to associate
PPE_ASSOC_MIN_OVERLAP = _env_float("PPE_ASSOC_MIN_OVERLAP", 0.30)
# Seconds between duplicate violations for the same (track, ppe_type)
PPE_VIOLATION_COOLDOWN = _env_float("PPE_VIOLATION_COOLDOWN", 10.0)
# Frames a violation must persist before firing (debounce flicker)
PPE_VIOLATION_MIN_FRAMES = _env_int("PPE_VIOLATION_MIN_FRAMES", 3)
# Which PPE items to enforce (must match keys in PPE_TYPE_MAP)
PPE_REQUIRED_ITEMS = os.getenv("PPE_REQUIRED_ITEMS", "hardhat,mask,vest,gloves").split(",")

# Phase 1 backend scope: keep model classes intact, but ignore everything outside
# the active compliance set at inference/application level.
ACTIVE_PPE_CLASSES = {
    "Hardhat",
    "NO-Hardhat",
    "Mask",
    "NO-Mask",
    "Safety Vest",
    "NO-Safety Vest",
    "Gloves",
    "NO-Gloves",
}

# Class name → normalized ppe_type; ignored classes are kept in the trained model but
# deliberately excluded from the Phase 1 compliance pipeline.
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

# -------- Tracking --------
TRACK_DISTANCE_THRESHOLD = _env_float("TRACK_DISTANCE_THRESHOLD", 100.0)
TRACK_STALE_TIMEOUT = _env_float("TRACK_STALE_TIMEOUT", 3.0)

# -------- Events --------
EVENT_COOLDOWN = _env_float("EVENT_COOLDOWN", 2.0)

# -------- Database --------
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "factory.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
