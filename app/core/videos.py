"""Runtime video locations for demos and the live showcase."""
from __future__ import annotations

from pathlib import Path

from app.core.config import LOG_DIR, MODEL_DIR, REPO_ROOT

VIDEO_DIR = REPO_ROOT / "test-videos"
PERSON_MODEL = MODEL_DIR / "person.pt"

# One folder per use case. 07 reuses 03; 08 reuses 06 (same file, not copied).
STORES = {
    "ppe": VIDEO_DIR / "01_ppe",
    "person": VIDEO_DIR / "02_person",
    "zone": VIDEO_DIR / "03_restricted_zone",
    "product_counting": VIDEO_DIR / "04_product_counting",
    "machine_idle": VIDEO_DIR / "06_machine_idle",
    "downtime": VIDEO_DIR / "06_machine_idle",
}

ALIASES = {
    "worker_idle": "zone",
}

PREFERRED_NAMES = {
    "ppe": "ppe_construction_site.mp4",
    "person": "zone_multi_person.mp4",
    "zone": "worker_single_person.mp4",
}

# Full paths that live outside the per-use-case folder.
# 06/08 used to play the static empty-belt clip. That file looks like a
# running conveyor (baked-in blur) but pixels barely change, so optical
# flow stays under threshold and the HUD stays IDLE. Use a clip with
# boxes actually translating.
PREFERRED_PATHS = {
    "machine_idle": VIDEO_DIR / "Boxes_moving_on_conveyor_belt_20260910150847.mp4",
    "downtime": VIDEO_DIR / "Boxes_moving_on_conveyor_belt_20260910150847.mp4",
}

# Seconds to skip on loop. Person clip opens on desk close-ups; COCO person
# only fires once the camera pulls back (~16s).
START_OFFSET_S = {
    "person": 16.5,
}

__all__ = [
    "DEFAULT_VIDEOS",
    "LOG_DIR",
    "PERSON_MODEL",
    "STORES",
    "VIDEO_DIR",
    "default_video",
    "expected_path",
    "first_mp4",
    "require_video",
    "start_offset_seconds",
]


def start_offset_seconds(key: str) -> float:
    return float(START_OFFSET_S.get(_store_key(key), 0.0))


def _store_key(key: str) -> str:
    return ALIASES.get(key, key)


def first_mp4(folder: Path) -> Path | None:
    if not folder.is_dir():
        return None
    clips = sorted(folder.glob("*.mp4"))
    return clips[0] if clips else None


def default_video(key: str) -> Path | None:
    key = _store_key(key)
    preferred_path = PREFERRED_PATHS.get(key)
    if preferred_path is not None and preferred_path.exists():
        return preferred_path
    store = STORES[key]
    preferred = PREFERRED_NAMES.get(key)
    if preferred:
        named = store / preferred
        if named.exists():
            return named
    return first_mp4(store)


def expected_path(key: str) -> Path:
    key = _store_key(key)
    preferred_path = PREFERRED_PATHS.get(key)
    if preferred_path is not None:
        return preferred_path
    preferred = PREFERRED_NAMES.get(key)
    if preferred:
        return STORES[key] / preferred
    return STORES[key] / "video.mp4"


DEFAULT_VIDEOS = {
    key: (default_video(key) or expected_path(key))
    for key in ("ppe", "person", "zone", "worker_idle")
}


def require_video(key: str, explicit: str | None = None) -> Path:
    if explicit and str(explicit).isdigit():
        raise SystemExit(
            f"{key} needs a video file, not a webcam index.\n"
            f"  Expected folder: {expected_path(key).parent}"
        )
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Video not found: {path}")
        return path
    found = default_video(key)
    if found:
        return found
    raise SystemExit(f"No video for '{key}'. Expected folder: {expected_path(key).parent}")
