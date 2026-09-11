"""Still-image good/defect classifier trained on MVTec AD (YOLO-cls)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.core.config import DEVICE, MVTEC_ROOT, QUALITY_CATEGORY, QUALITY_MODEL_PATH, TEST_IMAGE_DIR
from app.detection.base import BaseDetector, DetectionResult

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def _folder_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def _interleave_by_folder(files: list[Path]) -> list[Path]:
    buckets: dict[str, list[Path]] = {}
    order: list[str] = []
    for path in sorted(files, key=lambda p: str(p).lower()):
        key = path.parent.name.lower()
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(path)
    mixed: list[Path] = []
    while any(buckets[k] for k in order):
        for key in order:
            if buckets[key]:
                mixed.append(buckets[key].pop(0))
    return mixed


def list_quality_stills(category: str | None = None) -> list[Path]:
    local = _folder_images(TEST_IMAGE_DIR / "defect") + _folder_images(TEST_IMAGE_DIR / "good")
    if local:
        return _interleave_by_folder(local)
    wanted = category or QUALITY_CATEGORY
    names = []
    for name in (wanted, "hazelnut", "bottle"):
        if name not in names:
            names.append(name)
    if MVTEC_ROOT.is_dir():
        names.extend(sorted(p.name for p in MVTEC_ROOT.iterdir() if p.is_dir() and p.name not in names))
    for name in names:
        test = MVTEC_ROOT / name / "test"
        if not test.is_dir():
            continue
        files: list[Path] = []
        for sub in sorted(test.iterdir()):
            if sub.is_dir():
                files.extend(_folder_images(sub))
        if files:
            return _interleave_by_folder(files)
    return []


def quality_source_dir() -> Path | None:
    local = _folder_images(TEST_IMAGE_DIR / "defect") + _folder_images(TEST_IMAGE_DIR / "good")
    if local:
        return TEST_IMAGE_DIR
    files = list_quality_stills()
    if not files:
        return None
    # MVTec: .../<category>/test/<kind>/file.png → parents[1] is test/
    return files[0].parents[1] if len(files[0].parents) >= 2 else files[0].parent


def quality_ready() -> bool:
    return QUALITY_MODEL_PATH.exists() and quality_source_dir() is not None


class QualityDetector(BaseDetector):
    name = "quality"
    frame_stride = 1

    def __init__(self, camera_id: str = "cam", model_path=None):
        super().__init__(camera_id)
        self.model_path = model_path or QUALITY_MODEL_PATH
        self.model = None
        self._last: Dict[str, Any] = {"label": "unknown", "confidence": 0.0}
        self._last_sig = None
        self._last_rows: List[DetectionResult] = []

    def setup(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"No quality weights at {self.model_path}. "
                "Train first: python tools/training/quality/train_mvtec.py"
            )
        from ultralytics import YOLO

        print(f"[quality] loading {self.model_path}")
        self.model = YOLO(str(self.model_path))
        try:
            self.model.to(DEVICE)
        except Exception:
            pass

    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        if self.model is None:
            return []
        sig = (frame.shape, int(frame[::16, ::16].sum()))
        if sig == self._last_sig and self._last_rows:
            return list(self._last_rows)
        results = self.model(frame, verbose=False)
        label, conf = "unknown", 0.0
        if results:
            probs = getattr(results[0], "probs", None)
            if probs is not None:
                idx = int(probs.top1)
                conf = float(probs.top1conf)
                names = results[0].names
                label = names.get(idx, str(idx)) if isinstance(names, dict) else str(names[idx])
        self._last = {"label": label, "confidence": conf}
        self._last_sig = sig
        self._last_rows = [{
            "detector": self.name,
            "label": label,
            "confidence": conf,
            "bbox": [],
            "metadata": {"role": "quality", "ok": label.lower() == "good"},
        }]
        return list(self._last_rows)

    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state.update(self._last)
        return state
