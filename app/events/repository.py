"""SQLite event persistence."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import DATA_DIR
from app.events.models import CREATE_STATEMENTS

_lock = threading.Lock()


def db_path() -> Path:
    return Path(os.getenv("DB_PATH", str(DATA_DIR / "factory.db")))


def get_conn() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def cursor():
    conn = get_conn()
    try:
        with _lock:
            cur = conn.cursor()
            yield cur
            conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with cursor() as cur:
        for stmt in CREATE_STATEMENTS:
            cur.execute(stmt)


def insert_event(payload: Dict[str, Any]) -> int:
    with cursor() as cur:
        cur.execute(
            """INSERT INTO events
            (event_type, event_subtype, detector, label, confidence, camera_id,
             track_id, zone_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2, metadata_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.get("event_type"),
                payload.get("event_subtype"),
                payload.get("detector"),
                payload.get("label"),
                float(payload.get("confidence", 0.0)),
                payload.get("camera_id"),
                payload.get("track_id"),
                payload.get("zone_id"),
                payload["bbox"][0] if len(payload.get("bbox") or []) == 4 else None,
                payload["bbox"][1] if len(payload.get("bbox") or []) == 4 else None,
                payload["bbox"][2] if len(payload.get("bbox") or []) == 4 else None,
                payload["bbox"][3] if len(payload.get("bbox") or []) == 4 else None,
                json.dumps(payload.get("metadata") or {}),
                float(payload.get("timestamp", 0.0)),
            ),
        )
        return cur.lastrowid


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    bbox: List[float] = []
    for k in ("bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2"):
        v = d.pop(k, None)
        if v is not None:
            bbox.append(v)
    d["bbox"] = bbox if len(bbox) == 4 else []
    try:
        d["metadata"] = json.loads(d.pop("metadata_json") or "{}")
    except (TypeError, ValueError):
        d["metadata"] = {}
    ts = d.get("timestamp") or 0.0
    d["timestamp_ms"] = int(ts * 1000)
    return d


def list_events(limit: int = 50, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    q = "SELECT * FROM events"
    params: list = []
    if event_type:
        q += " WHERE event_type = ?"
        params.append(event_type)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    with cursor() as cur:
        cur.execute(q, params)
        rows = cur.fetchall()
    return [_row_to_dict(r) for r in rows]


def event_stats() -> Dict[str, Any]:
    with cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM events")
        total = cur.fetchone()["n"]
        cur.execute(
            "SELECT event_type, COUNT(*) AS n FROM events GROUP BY event_type ORDER BY n DESC"
        )
        by_type = {r["event_type"]: r["n"] for r in cur.fetchall()}
        cur.execute(
            """SELECT event_subtype, COUNT(*) AS n FROM events
               WHERE event_type = 'ppe_violation' AND event_subtype IS NOT NULL
               GROUP BY event_subtype ORDER BY n DESC"""
        )
        violations_by_subtype = {r["event_subtype"]: r["n"] for r in cur.fetchall()}
        cur.execute(
            "SELECT COUNT(DISTINCT track_id) AS n FROM events WHERE track_id IS NOT NULL"
        )
        unique_tracks = cur.fetchone()["n"]
    return {
        "total_events": total,
        "by_type": by_type,
        "violations_by_subtype": violations_by_subtype,
        "unique_tracks": unique_tracks,
    }
