"""FastAPI entry — wires camera, pipeline, detectors, event engine, DB, routes."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cameras, detectors, events, health, video
from app.camera.manager import CameraManager
from app.config import CAMERA_ID, VIDEO_SOURCE
from app.db.database import init_db
from app.detectors.ppe_detector import PPEDetector
from app.events.engine import EventEngine
from app.pipeline.runner import FramePipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[main] init db")
    init_db()

    print("[main] camera manager")
    cam_mgr = CameraManager()
    cam_mgr.add_camera(CAMERA_ID, VIDEO_SOURCE, autostart=True)
    app.state.camera_manager = cam_mgr

    print("[main] event engine")
    engine = EventEngine()
    app.state.event_engine = engine

    print("[main] pipeline (detectors: ppe)")
    ppe = PPEDetector(camera_id=CAMERA_ID)
    pipeline = FramePipeline(
        camera_manager=cam_mgr,
        event_engine=engine,
        detectors=[ppe],
        camera_id=CAMERA_ID,
    )
    pipeline.start()
    app.state.pipeline = pipeline

    print("[main] ready")
    try:
        yield
    finally:
        print("[main] shutdown")
        try:
            pipeline.stop()
        except Exception:
            pass
        try:
            cam_mgr.stop_all()
        except Exception:
            pass


app = FastAPI(title="Factory AI POC — Phase 1 (PPE)", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(events.router)
app.include_router(cameras.router)
app.include_router(detectors.router)
app.include_router(video.router)


@app.get("/")
def root():
    return {
        "name": "Factory AI POC",
        "phase": 1,
        "detectors": ["ppe"],
        "endpoints": ["/health", "/events", "/events/stats", "/cameras", "/detectors", "/video_feed"],
    }
