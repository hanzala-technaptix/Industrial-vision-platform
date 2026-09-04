"""PPE removal alerts — instant OK → missing transitions."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from app.alerts.base import AlertTracker
from app.rendering.detections import ppe_display_name


def _item_state(meta: dict, ppe_type: str) -> str:
    if ppe_type in (meta.get("violating") or []):
        return "violating"
    if ppe_type in (meta.get("compliant") or []):
        return "compliant"
    return "unknown"


class PPEAlertTracker(AlertTracker):
    def __init__(self, required_items: List[str], hold_seconds: float = 4.0):
        self.required = [i.strip().lower() for i in required_items if i.strip()]
        self.hold_seconds = hold_seconds
        self._prev: Dict[int, Dict[str, str]] = {}
        self._active: List[Tuple[float, str, int | None]] = []

    def update(self, detections: List[Dict[str, Any]]) -> List[str]:
        now = time.time()
        messages: List[str] = []

        for det in detections:
            if det.get("label") != "Person":
                continue
            meta = det.get("metadata") or {}
            if meta.get("role") != "person":
                continue
            tid = det.get("track_id")
            if tid is None:
                continue

            prev = self._prev.setdefault(tid, {})
            removed: List[str] = []

            for ppe_type in self.required:
                cur = _item_state(meta, ppe_type)
                was = prev.get(ppe_type, "unknown")

                if was == "compliant" and cur in ("violating", "unknown"):
                    removed.append(ppe_type)
                elif was != "violating" and cur == "violating":
                    removed.append(ppe_type)

                prev[ppe_type] = cur

            if removed:
                names = ", ".join(ppe_display_name(p) for p in removed)
                msg = f"ALERT: Person #{tid} - {names} REMOVED"
                messages.append(msg)
                self._active.append((now + self.hold_seconds, msg, tid))
                meta["alert_removed"] = removed

        self._active = [(exp, m, t) for exp, m, t in self._active if exp > now]
        banner = [m for _, m, _ in self._active[-5:]]
        for m in messages:
            if m not in banner:
                banner.insert(0, m)
        return banner[:5]
