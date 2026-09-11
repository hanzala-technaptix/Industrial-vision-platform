"""Product counting — carton tracks crossing a vertical line."""
from __future__ import annotations

from collections import deque
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
        self._gray_hist: deque = deque(maxlen=6)
        self._tracks: Dict[int, Dict[str, Any]] = {}
        self._next_id = 1
        self._count = 0

    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        h, w = frame.shape[:2]
        line_x = self.line_x if self.line_x is not None else w // 2
        min_area = max(self.min_area, int(0.005 * w * h))
        min_w, min_h = 0.045 * w, 0.055 * h
        y0, y1 = int(0.08 * h), int(0.82 * h)
        match_dist = max(self.match_dist, 0.14 * w)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        self._gray_hist.append(gray)
        if len(self._gray_hist) < 3:
            return [self._status_row(line_x, [])]

        ref = self._gray_hist[0]
        diff = cv2.absdiff(gray, ref)
        _, motion = cv2.threshold(diff, max(self.motion_threshold, 16), 255, cv2.THRESH_BINARY)

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        cardboard = cv2.inRange(hsv, (4, 20, 40), (40, 220, 250))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        motion = cv2.dilate(motion, kernel, iterations=3)
        mask = cv2.bitwise_and(cardboard, motion)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: List[Dict[str, Any]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if bw < min_w or bh < min_h:
                continue
            cy = y + bh / 2.0
            if cy < y0 or cy > y1:
                continue
            aspect = bw / max(float(bh), 1.0)
            if aspect < 0.3 or aspect > 3.2:
                continue
            cx = x + bw / 2.0
            detections.append({
                "cx": cx, "cy": cy,
                "bbox": [float(x), float(y), float(x + bw), float(y + bh)],
                "area": float(area),
            })

        detections = _nms(detections, iou=0.35)
        self._match_tracks(detections, line_x, match_dist)

        blobs: List[Dict[str, Any]] = []
        for tid, tr in self._tracks.items():
            if tr["missing"] > 0:
                continue
            blobs.append({
                "detector": self.name,
                "label": "Product",
                "confidence": min(1.0, tr["area"] / (min_area * 4)),
                "bbox": tr["bbox"],
                "track_id": tid,
                "metadata": {"role": "product_blob", "side": tr["side"]},
            })
        return blobs + [self._status_row(line_x, blobs)]

    def _match_tracks(
        self,
        detections: List[Dict[str, Any]],
        line_x: int,
        match_dist: float,
    ) -> None:
        unused = set(self._tracks)
        for det in detections:
            best_id, best_d = None, match_dist
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
                    "area": det["area"], "side": side, "counted": False,
                    "missing": 0,
                }
                continue
            unused.discard(best_id)
            tr = self._tracks[best_id]
            prev_cx = tr["cx"]
            crossed = (prev_cx - line_x) * (det["cx"] - line_x) < 0
            if crossed and not tr["counted"] and abs(det["cx"] - prev_cx) > 4:
                self._count += 1
                tr["counted"] = True
            tr.update(
                cx=det["cx"], cy=det["cy"], bbox=det["bbox"],
                area=det["area"], side=side, missing=0,
            )

        for tid in list(unused):
            self._tracks[tid]["missing"] += 1
            if self._tracks[tid]["missing"] > 10:
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
        self._gray_hist.clear()
        self._tracks.clear()
        self._next_id = 1
        self._count = 0


def _iou(a: List[float], b: List[float]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _nms(dets: List[Dict[str, Any]], iou: float) -> List[Dict[str, Any]]:
    ordered = sorted(dets, key=lambda d: d["area"], reverse=True)
    keep: List[Dict[str, Any]] = []
    for det in ordered:
        if any(_iou(det["bbox"], k["bbox"]) >= iou for k in keep):
            continue
        keep.append(det)
    return keep
