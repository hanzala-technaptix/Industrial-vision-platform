"""FastAPI dependency helpers."""
from __future__ import annotations

from fastapi import Request


def get_pipeline(request: Request):
    return getattr(request.app.state, "pipeline", None)


def get_camera_manager(request: Request):
    return getattr(request.app.state, "camera_manager", None)


def get_event_engine(request: Request):
    return getattr(request.app.state, "event_engine", None)
