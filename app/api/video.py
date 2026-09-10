"""MJPEG live stream."""
from __future__ import annotations

import time

import cv2
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.config import JPEG_QUALITY

router = APIRouter()
_BOUNDARY = "frame"


def _mjpeg_generator(holder):
    while True:
        pipeline = holder() if callable(holder) else holder
        frame = pipeline.get_latest_frame() if pipeline is not None else None
        if frame is None:
            time.sleep(0.05)
            continue
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        if not ok:
            time.sleep(0.05)
            continue
        chunk = buf.tobytes()
        yield (
            b"--" + _BOUNDARY.encode() + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(chunk)).encode() + b"\r\n\r\n"
            + chunk + b"\r\n"
        )
        time.sleep(0.03)


@router.get("/video_feed")
def video_feed(request: Request):
    app = request.app

    def current():
        session = getattr(app.state, "session", None)
        if session is not None:
            return session.get_pipeline()
        return getattr(app.state, "pipeline", None)

    return StreamingResponse(
        _mjpeg_generator(current),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
    )
