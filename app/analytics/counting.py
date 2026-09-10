"""Product counting — centroid tracks crossing a vertical line."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from app.detection.base import BaseDetector, DetectionResult


class ProductCountingDetector(BaseDetector):
    name = "product_counting"
    frame_stride = 1

    def __init__(
        self,
        camera_id: str = "cam",
        motion_threshold: int = 18,
        min_area: int = 250,
        line_x: Optional[int] = None,
        match_dist: float = 80.0,
    ):
        super().__init__(camera_id)
        self.motion_threshold = motion_threshold
        self.min_area = min_area
        self.line_x = line_x
        self.match_dist = match_dist
        self._prev_gray = None
        self._tracks: Dict[int, Dict[str, Any]] = {}
        self._next_id = 1
        self._count = 0

    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        h, w = frame.shape[:2]
        line_x = self.line_x if self.line_x is not None else w // 2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if self._prev_gray is None:
            self._prev_gray = gray
            return [self._status_row(line_x, [])]

        diff = cv2.absdiff(gray, self._prev_gray)
        _, thresh = cv2.threshold(diff, self.motion_threshold, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.dilate(thresh, kernel, iterations=2)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: List[Dict[str, Any]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            cx, cy = x + bw / 2.0, y + bh / 2.0
            detections.append({"cx": cx, "cy": cy, "bbox": [float(x), float(y), float(x + bw), float(y + bh)], "area": area})

        self._match_tracks(detections, line_x)
        self._prev_gray = gray

        blobs: List[Dict[str, Any]] = []
        for tid, tr in self._tracks.items():
            if tr["missing"] > 0:
                continue
            blobs.append({
                "detector": self.name,
                "label": "Product",
                "confidence": min(1.0, tr["area"] / (self.min_area * 4)),
                "bbox": tr["bbox"],
                "track_id": tid,
                "metadata": {"role": "product_blob", "side": tr["side"]},
            })
        return blobs + [self._status_row(line_x, blobs)]

    def _match_tracks(self, detections: List[Dict[str, Any]], line_x: int) -> None:
        unused = set(self._tracks)
        for det in detections:
            best_id, best_d = None, self.match_dist
            for tid in unused:
                tr = self._tracks[tid]
                d = float(np.hypot(det["cx"] - tr["cx"], det["cy"] - tr["cy"]))
                if d < best_d:
                    best_d, best_id = d, tid
            side = "left" if det["cx"] < line_x else "right"
            if best_id is None:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = {
                    "cx": det["cx"], "cy": det["cy"], "bbox": det["bbox"],
                    "area": det["area"], "side": side, "counted": False, "missing": 0,
                }
                continue
            unused.discard(best_id)
            tr = self._tracks[best_id]
            if tr["side"] != side and not tr["counted"]:
                self._count += 1
                tr["counted"] = True
            tr.update(cx=det["cx"], cy=det["cy"], bbox=det["bbox"], area=det["area"], side=side, missing=0)

        for tid in list(unused):
            self._tracks[tid]["missing"] += 1
            if self._tracks[tid]["missing"] > 12:
                del self._tracks[tid]

    def _status_row(self, line_x: int, blobs: List[Dict[str, Any]]) -> DetectionResult:
        return {
            "detector": self.name,
            "label": "LineCount",
            "confidence": 1.0,
            "bbox": [],
            "metadata": {
                "role": "counter",
                "count": self._count,
                "line_x": line_x,
                "blobs": len(blobs),
            },
        }

    def get_state(self) -> Dict[str, Any]:
        s = super().get_state()
        s.update({
            "count": self._count,
            "motion_threshold": self.motion_threshold,
            "min_area": self.min_area,
        })
        return s

    def reset(self) -> None:
        self._prev_gray = None
        self._tracks.clear()
        self._next_id = 1
        self._count = 0
