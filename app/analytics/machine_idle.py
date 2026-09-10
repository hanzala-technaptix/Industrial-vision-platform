"""Machine running / idle via optical flow in ROI."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from app.detection.base import BaseDetector, DetectionResult

# Farneback on a small gray frame. Score is mean flow in those pixels
# (not original-resolution pixels). 0.12 sits above a static belt (~0.06)
# and below a moving conveyor (~0.3+).
FLOW_WIDTH = 320


class MachineIdleDetector(BaseDetector):
    name = "machine_idle"
    frame_stride = 1

    def __init__(
        self,
        camera_id: str = "cam",
        idle_seconds: float = 0.8,
        motion_threshold: float = 0.15,
        roi_polygon: Optional[np.ndarray] = None,
        fps: float = 25.0,
        run_seconds: float = 0.35,
    ):
        super().__init__(camera_id)
        self.idle_seconds = idle_seconds
        self.run_seconds = run_seconds
        self.motion_threshold = motion_threshold
        self.roi_polygon = roi_polygon
        self.fps = max(float(fps), 1.0)
        self._prev_gray = None
        self._motion_history: list[float] = []
        self._quiet_s = 0.0
        self._busy_s = 0.0
        self._idle_duration = 0.0
        self._roi_mask = None
        self._roi_box = None
        self._last_state = "idle"
        self._last_motion = 0.0
        self._running_s = 0.0
        self._idle_s = 0.0
        self._last_frame_no: int | None = None

    def setup(self) -> None:
        pass

    def _ensure_roi(self, frame):
        if self.roi_polygon is not None and self._roi_mask is None:
            self._roi_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.fillPoly(self._roi_mask, [self.roi_polygon], 255)
            x, y, w, h = cv2.boundingRect(self.roi_polygon)
            self._roi_box = (x, y, w, h)

    def _flow_score(self, prev, gray, mask) -> float:
        h, w = gray.shape[:2]
        scale = FLOW_WIDTH / max(w, 1)
        if scale < 1.0:
            size = (FLOW_WIDTH, max(1, int(h * scale)))
            gray = cv2.resize(gray, size)
            prev = cv2.resize(prev, size)
            if mask is not None:
                mask = cv2.resize(mask, size)
        flow = cv2.calcOpticalFlowFarneback(
            prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        if mask is not None:
            valid = mask > 127
            if not np.any(valid):
                return 0.0
            mag = mag[valid]
        mean = float(np.mean(mag))
        busy = float(np.mean(mag > 0.45))
        return mean + busy

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
            motion_score = self._flow_score(prev_crop, gray_crop, mask_crop)

        self._prev_gray = gray
        self._motion_history.append(motion_score)
        if len(self._motion_history) > 5:
            self._motion_history.pop(0)
        smoothed = float(np.mean(self._motion_history))

        if self._last_frame_no is None:
            dt = 1.0 / self.fps
        else:
            dt = max(1, frame_count - self._last_frame_no) / self.fps
        self._last_frame_no = frame_count

        # Clip time, not wall clock: dt = frames_elapsed / fps.
        # Idle is the rest state. Need run_seconds of motion to go RUNNING,
        # idle_seconds of quiet to go back to IDLE.
        moving = smoothed >= self.motion_threshold
        if moving:
            self._busy_s += dt
            self._quiet_s = 0.0
        else:
            self._quiet_s += dt
            self._busy_s = 0.0

        if self._last_state == "idle":
            state = "active" if self._busy_s >= self.run_seconds else "idle"
        else:
            state = "idle" if self._quiet_s >= self.idle_seconds else "active"

        if state == "idle":
            self._idle_s += dt
            self._idle_duration = self._idle_s
        else:
            self._running_s += dt
            self._idle_duration = 0.0
        self._last_state = state
        self._last_motion = smoothed

        return [{
            "detector": self.name,
            "label": "Machine",
            "confidence": smoothed,
            "bbox": [],
            "metadata": {
                "role": "machine",
                "state": state,
                "motion": smoothed,
                "idle_seconds": self._idle_s,
                "idle_threshold": self.idle_seconds,
                "roi_polygon": self.roi_polygon.tolist() if self.roi_polygon is not None else None,
                "running_s": self._running_s,
                "idle_s": self._idle_s,
            },
        }]

    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state["motion_threshold"] = self.motion_threshold
        state["idle_seconds"] = self.idle_seconds
        state["state"] = self._last_state
        state["motion"] = self._last_motion
        state["idle_for"] = self._idle_s
        state["running_s"] = self._running_s
        state["idle_s"] = self._idle_s
        total = self._running_s + self._idle_s
        state["uptime_pct"] = (self._running_s / total * 100) if total else 0.0
        return state

    def reset(self) -> None:
        self._prev_gray = None
        self._motion_history.clear()
        self._quiet_s = 0.0
        self._busy_s = 0.0
        self._idle_duration = 0.0
        self._running_s = 0.0
        self._idle_s = 0.0
        self._last_frame_no = None
        self._last_state = "idle"
