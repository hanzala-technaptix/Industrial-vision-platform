"""FastAPI dependency helpers."""
from __future__ import annotations

from fastapi import Request


def get_pipeline(request: Request):
    session = getattr(request.app.state, "session", None)
    if session is not None:
        return session.get_pipeline()
    return getattr(request.app.state, "pipeline", None)


def get_camera_manager(request: Request):
    return getattr(request.app.state, "camera_manager", None)


def get_session(request: Request):
    return getattr(request.app.state, "session", None)
