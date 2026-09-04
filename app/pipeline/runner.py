"""Live camera pipeline — background thread."""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

import cv2

from app.alerts.manager import AlertManager
from app.camera.manager import CameraManager
from app.core.config import FRAME_HEIGHT, FRAME_SKIP, FRAME_WIDTH
from app.detectors.base import BaseDetector
from app.events.engine import EventEngine
from app.pipeline.frame_processor import FrameProcessor


class FramePipeline:
    def __init__(
        self,
        camera_manager: CameraManager,
        event_engine: EventEngine,
        detectors: List[BaseDetector],
        camera_id: str,
        alert_manager: Optional[AlertManager] = None,
    ):
        self.camera_manager = camera_manager
        self.camera_id = camera_id
        self.processor = FrameProcessor(
            detectors=detectors,
            event_engine=event_engine,
            alert_manager=alert_manager,
            camera_id=camera_id,
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
        while self._running:
            frame = self.camera_manager.get_frame(self.camera_id)
            if frame is None:
                time.sleep(0.03)
                continue

            self._frame_count += 1
            if FRAME_SKIP > 1 and (self._frame_count % FRAME_SKIP) != 0:
                with self._lock:
                    if self._latest_annotated is None:
                        try:
                            self._latest_annotated = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
                        except Exception:
                            self._latest_annotated = frame
                continue

            try:
                frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
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
