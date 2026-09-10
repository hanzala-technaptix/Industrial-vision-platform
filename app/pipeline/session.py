"""Live showcase session — swap use case, camera clip, and detectors."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, Optional

from app.events.alerts import AlertManager
from app.events.ppe import PPEAlertTracker
from app.camera.manager import CameraManager
from app.core.config import CAMERA_ID, PPE_REQUIRED_ITEMS, VIDEO_SOURCE
from app.core.videos import start_offset_seconds
from app.events.engine import EventEngine
from app.pipeline.runner import FramePipeline
from app.pipelines.showcase import (
    UseCaseSpec,
    build_detectors,
    describe,
    get_spec,
    list_specs,
    post_draw_for,
    video_for,
)


class LiveSession:
    def __init__(self):
        self.camera_manager = CameraManager()
        self.event_engine = EventEngine()
        self.pipeline: Optional[FramePipeline] = None
        self.spec: Optional[UseCaseSpec] = None
        self.source: Optional[str] = None
        self._lock = threading.Lock()

    def catalog(self) -> list[dict]:
        current = self.spec.id if self.spec else None
        rows = []
        for spec in list_specs():
            row = describe(spec)
            row["active"] = spec.id == current
            rows.append(row)
        return rows

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            spec = self.spec
            pipe = self.pipeline
            source = self.source
        return {
            "current": spec.id if spec else None,
            "title": spec.title if spec else None,
            "source": source,
            "pipeline": pipe.stats() if pipe else None,
            "use_cases": self.catalog(),
        }

    def start(self, use_case_id: str, source: Optional[str] = None) -> Dict[str, Any]:
        spec = get_spec(use_case_id)
        resolved = self._resolve_source(spec, source)
        with self._lock:
            self._swap(spec, resolved)
        return self.snapshot()

    def _resolve_source(self, spec: UseCaseSpec, source: Optional[str]) -> str:
        if source:
            path = Path(source).expanduser()
            if path.exists():
                return str(path.resolve())
            return source
        found = video_for(spec)
        if found is not None:
            return str(found)
        raise FileNotFoundError(
            f"No video for '{spec.id}'. Expected {describe(spec)['expected_video']}"
        )

    def _swap(self, spec: UseCaseSpec, source: str) -> None:
        if self.pipeline is not None:
            try:
                self.pipeline.stop()
            except Exception:
                pass
            self.pipeline = None

        self.camera_manager.replace_camera(
            CAMERA_ID,
            source,
            autostart=True,
            start_sec=start_offset_seconds(spec.video_key),
        )
        detectors = build_detectors(spec, CAMERA_ID)
        alerts = None
        if spec.alerts:
            alerts = AlertManager([PPEAlertTracker(PPE_REQUIRED_ITEMS)])

        pipeline = FramePipeline(
            camera_manager=self.camera_manager,
            event_engine=self.event_engine,
            detectors=detectors,
            camera_id=CAMERA_ID,
            alert_manager=alerts,
            post_draw=post_draw_for(spec),
        )
        pipeline.start()
        self.pipeline = pipeline
        self.spec = spec
        self.source = source

    def stop(self) -> None:
        with self._lock:
            if self.pipeline is not None:
                try:
                    self.pipeline.stop()
                except Exception:
                    pass
                self.pipeline = None
            try:
                self.camera_manager.stop_all()
            except Exception:
                pass

    def get_pipeline(self) -> Optional[FramePipeline]:
        return self.pipeline


def initial_use_case() -> str:
    import os

    requested = (os.getenv("USE_CASE") or "ppe").strip().lower()
    if requested in {s.id for s in list_specs()} and video_for(get_spec(requested)):
        return requested
    for spec in list_specs():
        if video_for(spec):
            return spec.id
    return "ppe"


def initial_source(use_case_id: str) -> Optional[str]:
    if isinstance(VIDEO_SOURCE, str) and VIDEO_SOURCE and not str(VIDEO_SOURCE).isdigit():
        path = Path(VIDEO_SOURCE)
        if path.exists():
            return str(path.resolve())
    try:
        found = video_for(get_spec(use_case_id))
    except KeyError:
        found = None
    return str(found) if found else None
