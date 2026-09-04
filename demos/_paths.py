"""Shared paths for CEO demos."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = REPO_ROOT / "test-videos"
MACHINE_VIDEO_DIR = VIDEO_DIR / "machine"
MODEL_DIR = REPO_ROOT / "models" / "yolo"
LOG_DIR = REPO_ROOT / "logs"

DEFAULT_VIDEOS = {
    "ppe": VIDEO_DIR / "ppe_construction_site.mp4",
    "person_vehicle": VIDEO_DIR / "zone_multi_person.mp4",
    "zone": VIDEO_DIR / "worker_single_person.mp4",
    "worker_idle": VIDEO_DIR / "worker_single_person.mp4",
}

DEFAULT_YOLO = MODEL_DIR / "yolov8n.pt"


def default_machine_video() -> Path | None:
    """First .mp4 in test-videos/machine/ — real line footage only, never webcam."""
    if not MACHINE_VIDEO_DIR.is_dir():
        return None
    clips = sorted(MACHINE_VIDEO_DIR.glob("*.mp4"))
    return clips[0] if clips else None


def require_machine_video(explicit: str | None = None) -> Path:
    if explicit and explicit.isdigit():
        raise SystemExit(
            "Machine idle needs a real video file, not a webcam index.\n"
            f"  Add MP4 files under: {MACHINE_VIDEO_DIR}\n"
            "  Then run: python demos/06_machine_idle/run.py"
        )
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.exists():
            raise SystemExit(f"Video not found: {p}")
        return p
    found = default_machine_video()
    if found is None:
        raise SystemExit(
            "No machine video found.\n"
            f"  Put factory/line MP4 clips in: {MACHINE_VIDEO_DIR}\n"
            "  Free stock: Mixkit, Pexels, Pixabay (search 'factory conveyor').\n"
            "  Or: python demos/06_machine_idle/run.py --source path\\to\\your_clip.mp4"
        )
    return found
