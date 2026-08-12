"""SQLite table DDL for the events store."""

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
