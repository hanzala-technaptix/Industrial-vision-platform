"""Shared per-frame processing for demos and live pipeline."""
from __future__ import annotations

from typing import Callable, List, Optional

from app.events.alerts import AlertManager
from app.detection.base import BaseDetector
from app.events.engine import EventEngine
from app.pipeline.result import FrameResult
from app.rendering.overlays import render_alert_panel
from app.rendering.renderer import render_frame


def _draw_alert_banner(frame, alerts: List[str]):
    if frame is None or not alerts:
        return frame
    try:
        import cv2
    except Exception:
        return frame
    panel = render_alert_panel(alerts, width=min(520, max(200, frame.shape[1] - 20)))
    if panel is None:
        return frame
    ph, pw = panel.shape[:2]
    h, w = frame.shape[:2]
    if ph > h - 10 or pw > w - 10:
        scale = min((w - 20) / pw, (h - 20) / ph, 1.0)
        panel = cv2.resize(panel, (max(1, int(pw * scale)), max(1, int(ph * scale))))
        ph, pw = panel.shape[:2]
    y, x = 10, 10
    roi = frame[y : y + ph, x : x + pw]
    if roi.shape[:2] != panel.shape[:2]:
        return frame
    cv2.addWeighted(panel, 0.88, roi, 0.12, 0, roi)
    return frame


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
        annotated = _draw_alert_banner(annotated, alerts)
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
