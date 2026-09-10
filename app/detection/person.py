"""Person detection (COCO class 0 / Person only)."""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.config import PERSON_CONF_THRESHOLD, PERSON_INFER_IMGSZ, PERSON_MODEL_PATH
from app.core.bbox import is_valid_bbox
from app.detection.base import BaseDetector, DetectionResult
from app.models.yolo import load_yolo

DEFAULT_CLASSES = [0]


def _person_class_ids(model) -> list[int]:
    names = getattr(model, "names", None) or {}
    items = names.items() if isinstance(names, dict) else enumerate(names)
    ids = [int(i) for i, n in items if str(n).lower() in {"person", "people"}]
    return ids or list(DEFAULT_CLASSES)


class PersonDetector(BaseDetector):
    name = "person"
    frame_stride = 1

    def __init__(self, camera_id: str = "cam", conf: float | None = None, model_path=None):
        super().__init__(camera_id)
        self.conf = PERSON_CONF_THRESHOLD if conf is None else conf
        self.imgsz = PERSON_INFER_IMGSZ
        self.model_path = model_path or PERSON_MODEL_PATH
        self.model = None
        self._class_ids = list(DEFAULT_CLASSES)
        self._last_count = 0

    def setup(self) -> None:
        self.model = load_yolo(self.model_path, label="person")
        if self.model is not None:
            self._class_ids = _person_class_ids(self.model)

    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        if self.model is None:
            return []
        results = self.model(
            frame,
            conf=self.conf,
            iou=0.45,
            imgsz=self.imgsz,
            classes=self._class_ids,
            verbose=False,
        )
        out: List[DetectionResult] = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                try:
                    cls_id = int(box.cls[0].item())
                    raw = self.model.names.get(cls_id) if isinstance(self.model.names, dict) else self.model.names[cls_id]
                    label = "Person"
                    conf = float(box.conf[0].item())
                    xyxy = [float(v) for v in box.xyxy[0].tolist()]
                except Exception:
                    continue
                if not is_valid_bbox(xyxy):
                    continue
                if str(raw).lower() not in {"person", "people"} and cls_id not in self._class_ids:
                    continue
                out.append({
                    "detector": self.name,
                    "label": label,
                    "confidence": conf,
                    "bbox": xyxy,
                    "metadata": {"role": "object", "raw_label": str(raw)},
                })
        self._last_count = len(out)
        return out

    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state["conf"] = self.conf
        state["classes"] = self._class_ids
        state["count"] = self._last_count
        return state
