"""Frame rendering — compose detections + optional overlays."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from app.rendering.detections import draw_detections


def render_frame(
    frame,
    detections: List[Dict[str, Any]],
    *,
    post_draw: Optional[Callable] = None,
):
    if frame is None:
        return None
    out = draw_detections(frame.copy(), detections)
    if post_draw is not None:
        out = post_draw(out, detections)
    return out
