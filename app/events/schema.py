"""Unified event schema for the Factory AI POC."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EventSchema(BaseModel):
    id: Optional[int] = None
    event_type: str
    event_subtype: Optional[str] = None
    detector: str
    label: Optional[str] = None
    confidence: float = 0.0
    camera_id: str
    track_id: Optional[int] = None
    zone_id: Optional[str] = None
    bbox: List[float] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    def to_api(self) -> Dict[str, Any]:
        d = self.model_dump()
        d["timestamp_ms"] = int(self.timestamp * 1000)
        return d
