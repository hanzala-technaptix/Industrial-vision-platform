"""Threaded video capture with reconnect + backoff."""
from __future__ import annotations

import threading
import time
from typing import Any, Optional

import cv2


class VideoStream:
    def __init__(self, source: Any = 0, camera_id: str = "cam"):
        self.source = source
        self.camera_id = camera_id
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame = None
        self.running = False
        self.connected = False
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None
        self._delay = 1.0
        self._max_delay = 30.0
        self._frame_count = 0
        self._last_frame_time = 0.0

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True, name=f"vs-{self.camera_id}")
        self.thread.start()

    def _open(self) -> bool:
        try:
            self.cap = cv2.VideoCapture(self.source)
            if self.cap.isOpened():
                self.connected = True
                self._delay = 1.0
                print(f"[stream:{self.camera_id}] connected to {self.source}")
                return True
        except Exception as e:
            print(f"[stream:{self.camera_id}] open error: {e}")
        self.connected = False
        return False

    def _run(self) -> None:
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                if not self._open():
                    time.sleep(self._delay)
                    self._delay = min(self._delay * 2, self._max_delay)
                    continue
            try:
                ret, frame = self.cap.read()
            except Exception as e:
                print(f"[stream:{self.camera_id}] read error: {e}")
                ret, frame = False, None
            if ret and frame is not None:
                with self.lock:
                    self.frame = frame
                    self._frame_count += 1
                    self._last_frame_time = time.time()
            else:
                print(f"[stream:{self.camera_id}] read failed — reconnecting")
                self.connected = False
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                time.sleep(self._delay)
                self._delay = min(self._delay * 2, self._max_delay)

    def get_frame(self):
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def status(self) -> dict:
        with self.lock:
            fc = self._frame_count
            last = self._last_frame_time
        return {
            "camera_id": self.camera_id,
            "source": str(self.source),
            "connected": self.connected,
            "running": self.running,
            "frame_count": fc,
            "seconds_since_last_frame": (time.time() - last) if last else None,
        }

    def stop(self) -> None:
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.connected = False
