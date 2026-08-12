"""FramePipeline — single per-camera background loop."""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

import cv2

from app.camera.manager import CameraManager
from app.config import FRAME_HEIGHT, FRAME_SKIP, FRAME_WIDTH
from app.events.engine import EventEngine
from app.pipeline.base_detector import BaseDetector, DetectionResult
from app.utils.draw import draw_detections


class FramePipeline:
    def __init__(
        self,
        camera_manager: CameraManager,
        event_engine: EventEngine,
        detectors: List[BaseDetector],
        camera_id: str,
    ):
        self.camera_manager = camera_manager
        self.event_engine = event_engine
        self.detectors = detectors
        self.camera_id = camera_id
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_count = 0
        self._latest_annotated = None
        self._lock = threading.Lock()
        self._last_process_time = 0.0

    def start(self) -> None:
        if self._running:
            return
        for d in self.detectors:
            try:
                d.setup()
                print(f"[pipeline] detector {d.name} ready")
            except Exception as e:
                print(f"[pipeline] detector {d.name} setup FAILED: {e}")
                d.enabled = False
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"pipe-{self.camera_id}")
        self._thread.start()

    def _run(self) -> None:
        while self._running:
            frame = self.camera_manager.get_frame(self.camera_id)
            if frame is None:
                time.sleep(0.03)
                continue

            self._frame_count += 1
            if FRAME_SKIP > 1 and (self._frame_count % FRAME_SKIP) != 0:
                # still refresh latest_annotated with the raw frame so /video_feed stays live
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

            all_results: List[DetectionResult] = []
            for d in self.detectors:
                if not d.enabled:
                    continue
                if d.frame_stride > 1 and (self._frame_count % d.frame_stride) != 0:
                    continue
                try:
                    r = d.process(frame, self._frame_count)
                except Exception as e:
                    print(f"[pipeline] {d.name} process error: {e}")
                    continue
                for row in r:
                    row.setdefault("detector", d.name)
                all_results.extend(r)

            try:
                self.event_engine.process(all_results, camera_id=self.camera_id)
            except Exception as e:
                print(f"[pipeline] event engine error: {e}")

            annotated = draw_detections(frame.copy(), all_results)
            with self._lock:
                self._latest_annotated = annotated
                self._last_process_time = time.time()

        for d in self.detectors:
            try:
                d.cleanup()
            except Exception:
                pass

    def get_latest_frame(self):
        with self._lock:
            if self._latest_annotated is None:
                return None
            return self._latest_annotated.copy()

    def get_detector_states(self) -> List[Dict]:
        return [d.get_state() for d in self.detectors]

    def stats(self) -> Dict:
        return {
            "camera_id": self.camera_id,
            "running": self._running,
            "frames_seen": self._frame_count,
            "last_process_age_s": (time.time() - self._last_process_time) if self._last_process_time else None,
            "detectors": [d.name for d in self.detectors if d.enabled],
        }

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
