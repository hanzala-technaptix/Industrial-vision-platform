"""Live camera pipeline — background thread."""
from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional

import cv2

from app.events.alerts import AlertManager
from app.camera.manager import CameraManager
from app.core.config import FRAME_HEIGHT, FRAME_WIDTH
from app.detection.base import BaseDetector
from app.events.engine import EventEngine
from app.pipeline.frame_processor import FrameProcessor


def _fit_frame(frame, max_w: int, max_h: int):
    """Downscale keeping aspect ratio. Do not squash 16:9 into a short box."""
    h, w = frame.shape[:2]
    if w <= 0 or h <= 0:
        return frame
    scale = min(max_w / w, max_h / h, 1.0)
    if scale >= 0.999:
        return frame
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    # Portrait clips like 478x850 would become ~304x540 and starve YOLO.
    if min(nw, nh) < 480 and min(w, h) >= 400:
        return frame
    return cv2.resize(frame, (nw, nh))


class FramePipeline:
    def __init__(
        self,
        camera_manager: CameraManager,
        event_engine: EventEngine,
        detectors: List[BaseDetector],
        camera_id: str,
        alert_manager: Optional[AlertManager] = None,
        post_draw: Optional[Callable] = None,
        draw_alerts: bool = True,
    ):
        self.camera_manager = camera_manager
        self.camera_id = camera_id
        self.processor = FrameProcessor(
            detectors=detectors,
            event_engine=event_engine,
            alert_manager=alert_manager,
            camera_id=camera_id,
            post_draw=post_draw,
            draw_alerts=draw_alerts,
        )
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_count = 0
        self._latest_annotated = None
        self._latest_alerts: List[str] = []
        self._lock = threading.Lock()
        self._last_process_time = 0.0

    def start(self) -> None:
        if self._running:
            return
        try:
            self.processor.setup()
            for d in self.processor.detectors:
                print(f"[pipeline] detector {d.name} ready")
        except Exception as e:
            print(f"[pipeline] setup error: {e}")
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"pipe-{self.camera_id}"
        )
        self._thread.start()

    def _run(self) -> None:
        last_seq = -1
        while self._running:
            snap = getattr(self.camera_manager, "get_snapshot", None)
            if snap is not None:
                frame, seq = snap(self.camera_id)
            else:
                frame, seq = self.camera_manager.get_frame(self.camera_id), last_seq + 1
            if frame is None or seq == last_seq:
                time.sleep(0.01)
                continue
            last_seq = seq
            self._frame_count += 1

            try:
                frame = _fit_frame(frame, FRAME_WIDTH, FRAME_HEIGHT)
            except Exception:
                pass

            try:
                result = self.processor.process(frame, self._frame_count)
            except Exception as e:
                print(f"[pipeline] process error: {e}")
                continue

            with self._lock:
                self._latest_annotated = result.annotated
                self._latest_alerts = result.alerts
                self._last_process_time = time.time()

        self.processor.cleanup()

    def get_latest_frame(self):
        with self._lock:
            if self._latest_annotated is None:
                return None
            return self._latest_annotated.copy()

    def get_latest_alerts(self) -> List[str]:
        with self._lock:
            return list(self._latest_alerts)

    def get_detector_states(self) -> List[Dict]:
        return [d.get_state() for d in self.processor.detectors]

    def stats(self) -> Dict:
        return {
            "camera_id": self.camera_id,
            "running": self._running,
            "frames_seen": self._frame_count,
            "last_process_age_s": (time.time() - self._last_process_time) if self._last_process_time else None,
            "detectors": [d.name for d in self.processor.detectors if d.enabled],
        }

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
