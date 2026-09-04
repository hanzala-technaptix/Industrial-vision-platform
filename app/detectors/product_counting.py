"""Product counting — motion-blob line-cross counter for conveyor footage.

Not tracker-based (which would need consistent item identity across frames);
uses simple frame-diff blobs and tracks which side of a vertical line the
largest blob is on. Good enough for CEO demos on typical conveyor clips.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from app.detectors.base import BaseDetector, DetectionResult


class ProductCountingDetector(BaseDetector):
    name = "product_counting"
    frame_stride = 1

    def __init__(
        self,
        camera_id: str = "cam",
        motion_threshold: int = 25,
        min_area: int = 400,
        line_x: Optional[int] = None,
    ):
        super().__init__(camera_id)
        self.motion_threshold = motion_threshold
        self.min_area = min_area
        self.line_x = line_x  # None = auto (frame center) on first frame
        self._prev_gray = None
        self._prev_side: Dict[int, str] = {}
        self._count = 0

    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        h, w = frame.shape[:2]
        line_x = self.line_x if self.line_x is not None else w // 2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self._prev_gray is None:
            self._prev_gray = gray
            return [self._status_row(line_x, [])]

        diff = cv2.absdiff(gray, self._prev_gray)
        _, thresh = cv2.threshold(diff, self.motion_threshold, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        blobs: List[Dict[str, Any]] = []
        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area < self.min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            cx = x + bw // 2
            side = "left" if cx < line_x else "right"
            prev = self._prev_side.get(i)
            crossed = prev is not None and prev != side
            if crossed:
                self._count += 1
            self._prev_side[i] = side
            blobs.append({
                "detector": self.name,
                "label": "Product",
                "confidence": min(1.0, area / (self.min_area * 4)),
                "bbox": [float(x), float(y), float(x + bw), float(y + bh)],
                "metadata": {"role": "product_blob", "side": side, "crossed": crossed, "area": area},
            })

        self._prev_gray = gray
        return blobs + [self._status_row(line_x, blobs)]

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
        self._prev_side.clear()
        self._count = 0
