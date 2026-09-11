"""Restricted zone — person foot point inside polygon."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from app.core.config import PERSON_MODEL_PATH
from app.core.bbox import is_valid_bbox
from app.detection.base import BaseDetector, DetectionResult
from app.detection.person import PersonDetector


def point_in_polygon(point, polygon) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def default_zone(frame) -> np.ndarray:
    h, w = frame.shape[:2]
    return np.array(
        [
            [int(w * 0.05), int(h * 0.05)],
            [int(w * 0.95), int(h * 0.05)],
            [int(w * 0.95), int(h * 0.95)],
            [int(w * 0.05), int(h * 0.95)],
        ],
        dtype=np.int32,
    )


class ZoneDetector(BaseDetector):
    name = "zone"
    frame_stride = 1

    def __init__(
        self,
        camera_id: str = "cam",
        zone_polygon: Optional[np.ndarray] = None,
        conf: float = 0.35,
    ):
        super().__init__(camera_id)
        self.zone = zone_polygon
        self._person = PersonDetector(camera_id, conf=conf, model_path=PERSON_MODEL_PATH)
        self._last_present = False
        self._last_person_count = 0

    def setup(self) -> None:
        self._person.setup()

    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        if self.zone is None:
            self.zone = default_zone(frame)

        raw = self._person.process(frame, frame_count)
        present = False
        for det in raw:
            bbox = det.get("bbox")
            if not is_valid_bbox(bbox) or str(det.get("label") or "").lower() != "person":
                continue
            x1, y1, x2, y2 = bbox
            foot = ((x1 + x2) / 2, y2)
            if point_in_polygon(foot, self.zone):
                present = True
                det.setdefault("metadata", {})["in_zone"] = True
            else:
                det.setdefault("metadata", {})["in_zone"] = False

        raw.append({
            "detector": self.name,
            "label": "Zone",
            "confidence": 1.0 if present else 0.0,
            "bbox": [],
            "metadata": {
                "role": "zone",
                "present": present,
                "polygon": self.zone.tolist(),
            },
        })
        for row in raw:
            row["detector"] = self.name
        self._last_present = present
        self._last_person_count = sum(1 for d in raw if str(d.get("label") or "").lower() == "person")
        return raw

    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state["zone_set"] = self.zone is not None
        state["present"] = self._last_present
        state["person_count"] = self._last_person_count
        return state
