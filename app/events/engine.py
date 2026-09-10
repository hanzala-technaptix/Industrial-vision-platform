"""EventEngine — deduplicated persistent events from detector output."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from app.core.config import PPE_VIOLATION_COOLDOWN, PPE_VIOLATION_MIN_FRAMES
from app.events.models import EventSchema
from app.events.repository import insert_event


class EventEngine:
    def __init__(self):
        self._per_pair: Dict[Tuple[int, str], Dict[str, Any]] = defaultdict(
            lambda: {"streak": 0, "last_state": "unknown", "last_event_ts": 0.0, "was_violating": False}
        )
        self._recent: List[Dict[str, Any]] = []
        self._recent_max = 200

    def _persist(self, ev: EventSchema) -> None:
        try:
            new_id = insert_event(ev.model_dump())
            ev.id = new_id
        except Exception as e:
            print(f"[events] persist failed: {e}")
        self._recent.append(ev.to_api())
        if len(self._recent) > self._recent_max:
            self._recent = self._recent[-self._recent_max:]

    def _emit_ppe_event(
        self,
        *,
        event_type: str,
        event_subtype: str,
        camera_id: str,
        track_id: int,
        confidence: float,
        bbox: List[float],
        metadata: Dict[str, Any],
    ) -> None:
        ev = EventSchema(
            event_type=event_type,
            event_subtype=event_subtype,
            detector="ppe",
            label="Person",
            confidence=confidence,
            camera_id=camera_id,
            track_id=track_id,
            bbox=bbox,
            metadata=metadata,
        )
        self._persist(ev)

    def process(self, detections: List[Dict[str, Any]], camera_id: str) -> None:
        now = time.time()
        persons = [
            d for d in detections
            if d.get("detector") == "ppe"
            and (d.get("metadata") or {}).get("role") == "person"
        ]
        seen_pairs: set = set()

        for person in persons:
            tid = person.get("track_id")
            if tid is None:
                continue
            meta = person.get("metadata") or {}
            bbox = person.get("bbox") or []
            conf = float(person.get("confidence") or 0.0)
            violating: List[str] = list(meta.get("violating") or [])
            compliant: List[str] = list(meta.get("compliant") or [])

            for ppe_type in violating:
                key = (tid, ppe_type)
                seen_pairs.add(key)
                st = self._per_pair[key]
                if st["last_state"] == "violating":
                    st["streak"] += 1
                else:
                    st["streak"] = 1
                st["last_state"] = "violating"

                fresh = not st["was_violating"] and st["streak"] >= PPE_VIOLATION_MIN_FRAMES
                cooled_down = (now - st["last_event_ts"]) >= PPE_VIOLATION_COOLDOWN
                if fresh or (st["was_violating"] and cooled_down):
                    self._emit_ppe_event(
                        event_type="ppe_violation",
                        event_subtype=f"no_{ppe_type}",
                        camera_id=camera_id,
                        track_id=tid,
                        confidence=conf,
                        bbox=bbox,
                        metadata={
                            "ppe_type": ppe_type,
                            "violating": violating,
                            "compliant": compliant,
                            "compliance_ratio": meta.get("compliance_ratio"),
                            "streak_frames": st["streak"],
                            "trigger": "fresh_violation" if fresh else "cooldown_repeat",
                        },
                    )
                    st["last_event_ts"] = now
                    st["was_violating"] = True

            for ppe_type in compliant:
                key = (tid, ppe_type)
                seen_pairs.add(key)
                st = self._per_pair[key]
                if st["last_state"] != "compliant":
                    st["streak"] = 1
                else:
                    st["streak"] += 1
                st["last_state"] = "compliant"
                if st["was_violating"] and st["streak"] >= PPE_VIOLATION_MIN_FRAMES:
                    self._emit_ppe_event(
                        event_type="ppe_compliant",
                        event_subtype=f"recovered_{ppe_type}",
                        camera_id=camera_id,
                        track_id=tid,
                        confidence=conf,
                        bbox=bbox,
                        metadata={
                            "ppe_type": ppe_type,
                            "compliant": compliant,
                            "violating": violating,
                            "trigger": "recovery",
                        },
                    )
                    st["was_violating"] = False
                    st["last_event_ts"] = now

        for key, st in list(self._per_pair.items()):
            if key not in seen_pairs:
                st["streak"] = 0
                st["last_state"] = "unknown"

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self._recent[-limit:]))
