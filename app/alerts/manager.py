"""Coordinates alert trackers for one pipeline session."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.alerts.base import AlertTracker


class AlertManager:
    def __init__(self, trackers: Optional[List[AlertTracker]] = None):
        self.trackers = trackers or []

    def update(self, detections: List[Dict[str, Any]]) -> List[str]:
        messages: List[str] = []
        for tracker in self.trackers:
            messages.extend(tracker.update(detections))
        # De-dupe while preserving order
        seen: set[str] = set()
        out: List[str] = []
        for msg in messages:
            if msg not in seen:
                seen.add(msg)
                out.append(msg)
        return out[:8]
