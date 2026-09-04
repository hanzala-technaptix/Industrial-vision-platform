"""FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.alerts.manager import AlertManager
from app.alerts.ppe import PPEAlertTracker
from app.api import events, routes, video
from app.camera.manager import CameraManager
from app.core.config import CAMERA_ID, PPE_REQUIRED_ITEMS, VIDEO_SOURCE
from app.detectors.ppe import PPEDetector
from app.events.engine import EventEngine
from app.events.repository import init_db
from app.pipeline.runner import FramePipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    cam_mgr = CameraManager()
    cam_mgr.add_camera(CAMERA_ID, VIDEO_SOURCE, autostart=True)
    app.state.camera_manager = cam_mgr

    engine = EventEngine()
    app.state.event_engine = engine

    ppe = PPEDetector(camera_id=CAMERA_ID)
    alerts = AlertManager([PPEAlertTracker(PPE_REQUIRED_ITEMS)])
    pipeline = FramePipeline(
        camera_manager=cam_mgr,
        event_engine=engine,
        detectors=[ppe],
        camera_id=CAMERA_ID,
        alert_manager=alerts,
    )
    pipeline.start()
    app.state.pipeline = pipeline

    try:
        yield
    finally:
        try:
            pipeline.stop()
        except Exception:
            pass
        try:
            cam_mgr.stop_all()
        except Exception:
            pass


app = FastAPI(title="Industrial Vision AI", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(events.router)
app.include_router(video.router)
