"""Person and vehicle detection (COCO)."""
from __future__ import annotations

from typing import Any, Dict, List

from app.core.config import DEVICE, PERSON_MODEL_PATH
from app.core.bbox import is_valid_bbox
from app.detectors.base import BaseDetector, DetectionResult

# COCO: person=0, bicycle=1, car=2, motorcycle=3, bus=5, truck=7
DEFAULT_CLASSES = [0, 1, 2, 3, 5, 7]


class PersonDetector(BaseDetector):
    name = "person"
    frame_stride = 1

    def __init__(self, camera_id: str = "cam", conf: float = 0.35, model_path=None):
        super().__init__(camera_id)
        self.conf = conf
        self.model_path = model_path or PERSON_MODEL_PATH
        self.model = None

    def setup(self) -> None:
        from ultralytics import YOLO

        path = self.model_path
        if not path.exists():
            print("[person] downloading yolov8n")
            self.model = YOLO("yolov8n.pt")
        else:
            print(f"[person] loading {path}")
            self.model = YOLO(str(path))
        try:
            self.model.to(DEVICE)
        except Exception:
            pass

    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        if self.model is None:
            return []
        results = self.model(frame, conf=self.conf, classes=DEFAULT_CLASSES, verbose=False)
        out: List[DetectionResult] = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                try:
                    cls_id = int(box.cls[0].item())
                    label = self.model.names.get(cls_id) if isinstance(self.model.names, dict) else self.model.names[cls_id]
                    conf = float(box.conf[0].item())
                    xyxy = [float(v) for v in box.xyxy[0].tolist()]
                except Exception:
                    continue
                if not is_valid_bbox(xyxy):
                    continue
                out.append({
                    "detector": self.name,
                    "label": str(label),
                    "confidence": conf,
                    "bbox": xyxy,
                    "metadata": {"role": "object"},
                })
        return out

    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state["conf"] = self.conf
        state["classes"] = DEFAULT_CLASSES
        return state
