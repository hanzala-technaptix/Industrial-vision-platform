"""Core API routes."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.dependencies import get_camera_manager, get_pipeline

router = APIRouter()


@router.get("/")
def root():
    return {
        "name": "Industrial Vision AI",
        "detectors": ["ppe", "person", "zone", "machine_idle"],
        "endpoints": ["/health", "/events", "/events/stats", "/cameras", "/detectors", "/video_feed"],
    }


@router.get("/health")
def health(request: Request):
    pipe = get_pipeline(request)
    cams = get_camera_manager(request)
    return {
        "status": "healthy" if pipe is not None else "starting",
        "pipeline": pipe.stats() if pipe is not None else None,
        "cameras": cams.list_cameras() if cams is not None else [],
    }


@router.get("/cameras")
def list_cameras(request: Request):
    cams = get_camera_manager(request)
    return {"cameras": cams.list_cameras() if cams is not None else []}


@router.get("/detectors")
def get_detectors(request: Request):
    pipe = get_pipeline(request)
    if pipe is None:
        return {"detectors": []}
    return {"detectors": pipe.get_detector_states()}
