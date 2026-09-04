"""Event schema and database DDL."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

CREATE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type    TEXT NOT NULL,
        event_subtype TEXT,
        detector      TEXT NOT NULL,
        label         TEXT,
        confidence    REAL DEFAULT 0.0,
        camera_id     TEXT NOT NULL,
        track_id      INTEGER,
        zone_id       TEXT,
        bbox_x1 REAL, bbox_y1 REAL, bbox_x2 REAL, bbox_y2 REAL,
        metadata_json TEXT,
        timestamp     REAL NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);",
    "CREATE INDEX IF NOT EXISTS idx_events_cam ON events(camera_id);",
    "CREATE INDEX IF NOT EXISTS idx_events_track ON events(track_id);",
]


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
