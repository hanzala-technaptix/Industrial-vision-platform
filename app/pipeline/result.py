"""Per-frame pipeline output."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class FrameResult:
    detections: List[Dict[str, Any]] = field(default_factory=list)
    annotated: Any = None
    alerts: List[str] = field(default_factory=list)
    frame_no: int = 0
