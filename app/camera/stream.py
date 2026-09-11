"""Threaded video capture with reconnect + backoff."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Optional

import cv2

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov"}


def _is_file_source(source: Any) -> bool:
    if isinstance(source, (list, tuple)):
        return True
    if isinstance(source, int):
        return False
    text = str(source)
    if text.isdigit():
        return False
    lower = text.lower()
    if lower.startswith(("rtsp://", "http://", "https://", "rtmp://")):
        return False
    path = Path(text)
    return path.exists() or path.suffix.lower() in VIDEO_EXTS


def _interleave_by_folder(files: list[Path]) -> list[Path]:
    """Round-robin across folders (crack, cut, good, hole, …) so classes mix."""
    buckets: dict[str, list[Path]] = {}
    order: list[str] = []
    for path in sorted(files, key=lambda p: str(p).lower()):
        key = path.parent.name.lower()
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(path)
    mixed: list[Path] = []
    while any(buckets[k] for k in order):
        for key in order:
            if buckets[key]:
                mixed.append(buckets[key].pop(0))
    return mixed


def list_image_files(source: Any) -> list[Path]:
    path = Path(str(source))
    if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
        return [path]
    if not path.is_dir():
        return []
    files = [
        p for p in path.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]
    return _interleave_by_folder(files)


class VideoStream:
    def __init__(self, source: Any = 0, camera_id: str = "cam", start_sec: float = 0.0):
        if isinstance(source, (list, tuple)):
            self._playlist = [str(p) for p in source if str(p)]
            self._playlist_i = 0
            self.source = self._playlist[0] if self._playlist else source
        else:
            self._playlist = None
            self._playlist_i = 0
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
        self._images = [] if self._playlist else list_image_files(self.source)
        self._hold_s = 2.5
        self._start_sec = max(0.0, float(start_sec or 0.0))

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
                self._seek_start()
                print(f"[stream:{self.camera_id}] connected to {self.source}")
                return True
        except Exception as e:
            print(f"[stream:{self.camera_id}] open error: {e}")
        self.connected = False
        return False

    def _seek_start(self) -> None:
        if self.cap is None:
            return
        if self._start_sec > 0:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, self._start_sec * 1000.0)
        else:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def _run(self) -> None:
        if self._images:
            self._run_stills()
            return
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                if not self._open():
                    time.sleep(self._delay)
                    self._delay = min(self._delay * 2, self._max_delay)
                    continue
            t0 = time.perf_counter()
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
                fps = self.cap.get(cv2.CAP_PROP_FPS) if self.cap is not None else 0.0
                period = 1.0 / fps if fps and fps > 1.0 else 0.04
                wait = period - (time.perf_counter() - t0)
                if wait > 0:
                    time.sleep(wait)
            elif _is_file_source(self.source) and self.cap is not None:
                if self._playlist and len(self._playlist) > 1:
                    if self.cap is not None:
                        self.cap.release()
                        self.cap = None
                    self._playlist_i = (self._playlist_i + 1) % len(self._playlist)
                    self.source = self._playlist[self._playlist_i]
                    print(f"[stream:{self.camera_id}] next clip {self.source}")
                else:
                    self._seek_start()
            else:
                print(f"[stream:{self.camera_id}] read failed — reconnecting")
                self.connected = False
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                time.sleep(self._delay)
                self._delay = min(self._delay * 2, self._max_delay)

    def _run_stills(self) -> None:
        print(f"[stream:{self.camera_id}] stills {len(self._images)} from {self.source}")
        self.connected = True
        idx = 0
        while self.running and self._images:
            path = self._images[idx % len(self._images)]
            frame = cv2.imread(str(path))
            if frame is not None:
                with self.lock:
                    self.frame = frame
                    self._frame_count += 1
                    self._last_frame_time = time.time()
            idx += 1
            deadline = time.time() + self._hold_s
            while self.running and time.time() < deadline:
                time.sleep(0.05)

    def get_frame(self):
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def snapshot(self):
        with self.lock:
            if self.frame is None:
                return None, 0
            return self.frame.copy(), self._frame_count

    def status(self) -> dict:
        with self.lock:
            fc = self._frame_count
            last = self._last_frame_time
        return {
            "camera_id": self.camera_id,
            "source": " | ".join(self._playlist) if self._playlist else str(self.source),
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
