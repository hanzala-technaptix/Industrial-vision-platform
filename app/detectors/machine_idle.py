"""Machine running / idle via optical flow in ROI."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from app.detectors.base import BaseDetector, DetectionResult


class MachineIdleDetector(BaseDetector):
    name = "machine_idle"
    frame_stride = 1

    def __init__(
        self,
        camera_id: str = "cam",
        idle_seconds: float = 3.0,
        motion_threshold: float = 0.5,
        roi_polygon: Optional[np.ndarray] = None,
    ):
        super().__init__(camera_id)
        self.idle_seconds = idle_seconds
        self.motion_threshold = motion_threshold
        self.roi_polygon = roi_polygon
        self._prev_gray = None
        self._motion_history: list[float] = []
        self._idle_start: float | None = None
        self._idle_duration = 0.0
        self._roi_mask = None
        self._roi_box = None

    def setup(self) -> None:
        pass

    def _ensure_roi(self, frame):
        if self.roi_polygon is not None and self._roi_mask is None:
            self._roi_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.fillPoly(self._roi_mask, [self.roi_polygon], 255)
            x, y, w, h = cv2.boundingRect(self.roi_polygon)
            self._roi_box = (x, y, w, h)

    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        self._ensure_roi(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 0)

        if self._roi_mask is not None:
            x, y, w, h = self._roi_box
            gray_crop = gray[y : y + h, x : x + w]
            mask_crop = self._roi_mask[y : y + h, x : x + w]
            prev_crop = self._prev_gray[y : y + h, x : x + w] if self._prev_gray is not None else None
        else:
            gray_crop, mask_crop, prev_crop = gray, None, self._prev_gray

        motion_score = 0.0
        if prev_crop is not None and gray_crop.shape == prev_crop.shape and gray_crop.size > 0:
            flow = cv2.calcOpticalFlowFarneback(
                prev_crop, gray_crop, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            if mask_crop is not None:
                valid = mask_crop > 0
                motion_score = float(np.sum(mag[valid]) / max(np.count_nonzero(valid), 1))
            else:
                motion_score = float(np.mean(mag))

        self._prev_gray = gray
        self._motion_history.append(motion_score)
        if len(self._motion_history) > 8:
            self._motion_history.pop(0)
        smoothed = float(np.mean(self._motion_history))

        if smoothed < self.motion_threshold:
            self._idle_start = self._idle_start or time.time()
            self._idle_duration = time.time() - self._idle_start
        else:
            self._idle_start = None
            self._idle_duration = 0.0

        state = "idle" if self._idle_duration >= self.idle_seconds else "active"

        return [{
            "detector": self.name,
            "label": "Machine",
            "confidence": smoothed,
            "bbox": [],
            "metadata": {
                "role": "machine",
                "state": state,
                "motion": smoothed,
                "idle_seconds": self._idle_duration,
                "idle_threshold": self.idle_seconds,
                "roi_polygon": self.roi_polygon.tolist() if self.roi_polygon is not None else None,
            },
        }]

    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state["motion_threshold"] = self.motion_threshold
        state["idle_seconds"] = self.idle_seconds
        return state

    def reset(self) -> None:
        self._prev_gray = None
        self._motion_history.clear()
        self._idle_start = None
        self._idle_duration = 0.0
