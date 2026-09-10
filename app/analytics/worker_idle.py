"""Worker active / idle / absent — YOLO person + Farneback optical flow inside the person ROI.

Fits BaseDetector so it runs through FrameProcessor exactly like PPE / machine
idle. Emits one row per frame with metadata.state ∈ {active, idle, absent}.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from app.core.bbox import is_valid_bbox
from app.core.config import PERSON_MODEL_PATH
from app.detection.base import BaseDetector, DetectionResult


class WorkerIdleDetector(BaseDetector):
    name = "worker_idle"
    frame_stride = 1

    def __init__(
        self,
        camera_id: str = "cam",
        idle_seconds: float = 8.0,
        motion_threshold: float = 0.003,
        person_conf: float = 0.35,
        detect_every: int = 10,
        model_path=None,
    ):
        super().__init__(camera_id)
        self.idle_seconds = idle_seconds
        self.motion_threshold = motion_threshold
        self.person_conf = person_conf
        self.detect_every = max(1, detect_every)
        self.model_path = model_path or PERSON_MODEL_PATH
        self.model = None

        self._prev_gray = None
        self._person_box: Optional[np.ndarray] = None
        self._motion_history: List[float] = []
        self._idle_start: Optional[float] = None
        self._idle_duration: float = 0.0
        self._last_state = "absent"
        self._last_motion = 0.0

    def setup(self) -> None:
        from ultralytics import YOLO

        self.model = YOLO(str(self.model_path)) if self.model_path.exists() else YOLO("yolov8n.pt")

    def _detect_person(self, frame) -> Optional[np.ndarray]:
        results = self.model(frame, conf=self.person_conf, classes=[0], verbose=False)
        best_box, best_conf = None, 0.0
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf > best_conf:
                    best_conf = conf
                    best_box = box.xyxy[0].cpu().numpy()
        return best_box

    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        if self.model is None:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 0)

        if frame_count % self.detect_every == 0 or self._person_box is None:
            self._person_box = self._detect_person(frame)

        motion_score = 0.0
        person_bbox: List[float] = []
        if self._person_box is not None:
            x1, y1, x2, y2 = map(int, self._person_box)
            person_bbox = [float(x1), float(y1), float(x2), float(y2)]
            roi_gray = gray[y1:y2, x1:x2]
            roi_prev = self._prev_gray[y1:y2, x1:x2] if self._prev_gray is not None else None
            if roi_prev is not None and roi_gray.shape == roi_prev.shape and roi_gray.size > 0:
                flow = cv2.calcOpticalFlowFarneback(
                    roi_prev, roi_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                )
                mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                motion_score = float(np.mean(mag))

        self._motion_history.append(motion_score)
        if len(self._motion_history) > 8:
            self._motion_history.pop(0)
        smoothed = float(np.mean(self._motion_history))

        if self._person_box is None:
            state = "absent"
            self._idle_start = None
            self._idle_duration = 0.0
        else:
            if smoothed < self.motion_threshold:
                self._idle_start = self._idle_start or time.time()
                self._idle_duration = time.time() - self._idle_start
            else:
                self._idle_start = None
                self._idle_duration = 0.0
            state = "idle" if self._idle_duration >= self.idle_seconds else "active"

        self._last_state = state
        self._last_motion = smoothed
        self._prev_gray = gray

        return [{
            "detector": self.name,
            "label": "Worker",
            "confidence": smoothed,
            "bbox": person_bbox if is_valid_bbox(person_bbox) else [],
            "metadata": {
                "role": "worker",
                "state": state,
                "motion": smoothed,
                "idle_seconds": self._idle_duration,
                "idle_threshold": self.idle_seconds,
            },
        }]

    def get_state(self) -> Dict[str, Any]:
        s = super().get_state()
        s.update({
            "idle_seconds": self.idle_seconds,
            "motion_threshold": self.motion_threshold,
            "state": self._last_state,
            "motion": self._last_motion,
            "idle_for": self._idle_duration,
        })
        return s
