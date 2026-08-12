"""Registry of active VideoStreams. Single owner of cv2.VideoCapture per camera."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.camera.stream import VideoStream


class CameraManager:
    def __init__(self):
        self._streams: Dict[str, VideoStream] = {}

    def add_camera(self, camera_id: str, source: Any, autostart: bool = True) -> VideoStream:
        if camera_id in self._streams:
            return self._streams[camera_id]
        stream = VideoStream(source=source, camera_id=camera_id)
        self._streams[camera_id] = stream
        if autostart:
            stream.start()
        return stream

    def get_stream(self, camera_id: str) -> Optional[VideoStream]:
        return self._streams.get(camera_id)

    def get_frame(self, camera_id: str):
        s = self._streams.get(camera_id)
        return s.get_frame() if s else None

    def list_cameras(self) -> List[Dict[str, Any]]:
        return [s.status() for s in self._streams.values()]

    def any_camera_id(self) -> Optional[str]:
        return next(iter(self._streams.keys()), None)

    def stop_all(self) -> None:
        for s in list(self._streams.values()):
            s.stop()
        self._streams.clear()
