"""Shared per-frame processing for demos and live pipeline."""
from __future__ import annotations

from typing import Callable, List, Optional

from app.alerts.manager import AlertManager
from app.detectors.base import BaseDetector
from app.events.engine import EventEngine
from app.pipeline.result import FrameResult
from app.rendering.renderer import render_frame


class FrameProcessor:
    def __init__(
        self,
        detectors: List[BaseDetector],
        event_engine: Optional[EventEngine] = None,
        alert_manager: Optional[AlertManager] = None,
        camera_id: str = "cam",
        post_draw: Optional[Callable] = None,
    ):
        self.detectors = detectors
        self.event_engine = event_engine
        self.alert_manager = alert_manager
        self.camera_id = camera_id
        self.post_draw = post_draw

    def setup(self) -> None:
        for d in self.detectors:
            if d.enabled:
                d.setup()

    def process(self, frame, frame_no: int) -> FrameResult:
        all_results = []
        for d in self.detectors:
            if not d.enabled:
                continue
            if d.frame_stride > 1 and (frame_no % d.frame_stride) != 0:
                continue
            rows = d.process(frame, frame_no)
            for row in rows:
                row.setdefault("detector", d.name)
            all_results.extend(rows)

        if self.event_engine is not None:
            self.event_engine.process(all_results, camera_id=self.camera_id)

        alerts: List[str] = []
        if self.alert_manager is not None:
            alerts = self.alert_manager.update(all_results)

        annotated = render_frame(frame, all_results, post_draw=self.post_draw)
        return FrameResult(
            detections=all_results,
            annotated=annotated,
            alerts=alerts,
            frame_no=frame_no,
        )

    def cleanup(self) -> None:
        for d in self.detectors:
            try:
                d.cleanup()
            except Exception:
                pass
