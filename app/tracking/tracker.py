"""Centroid-distance object tracker."""
from __future__ import annotations

import math
import time
from typing import Dict, List, Optional

from app.core.bbox import bbox_iou, is_valid_bbox


class TrackedObject:
    def __init__(self, obj_id: int, bbox: List[float]):
        self.id = obj_id
        self.bbox = bbox
        self.last_seen = time.time()
        self.first_seen = self.last_seen

    def update(self, bbox: List[float]) -> None:
        self.bbox = bbox
        self.last_seen = time.time()

    def is_stale(self, timeout: float) -> bool:
        return (time.time() - self.last_seen) > timeout

    def distance_to(self, bbox: List[float]) -> float:
        cxo = (self.bbox[0] + self.bbox[2]) / 2.0
        cyo = (self.bbox[1] + self.bbox[3]) / 2.0
        cxn = (bbox[0] + bbox[2]) / 2.0
        cyn = (bbox[1] + bbox[3]) / 2.0
        return math.sqrt((cxn - cxo) ** 2 + (cyn - cyo) ** 2)


class ObjectTracker:
    def __init__(self, distance_threshold: float = 160.0, stale_timeout: float = 0.8):
        self.objects: Dict[int, TrackedObject] = {}
        self.next_id = 0
        self.distance_threshold = distance_threshold
        self.stale_timeout = stale_timeout
        self.current_ids: set = set()

    def update(self, detections):
        current_ids = set()
        for det in detections:
            if not isinstance(det, dict):
                continue
            bbox = det.get("bbox")
            if not is_valid_bbox(bbox):
                continue
            best_id: Optional[int] = None
            best_key = None
            for oid, obj in self.objects.items():
                if oid in current_ids:
                    continue
                iou = bbox_iou(obj.bbox, bbox)
                dist = obj.distance_to(bbox)
                if iou >= 0.25:
                    key = (0, -iou, dist)
                elif dist < self.distance_threshold:
                    key = (1, dist, 0.0)
                else:
                    continue
                if best_key is None or key < best_key:
                    best_key = key
                    best_id = oid
            if best_id is not None:
                self.objects[best_id].update(bbox)
                det["track_id"] = best_id
                current_ids.add(best_id)
            else:
                new_id = self.next_id
                self.next_id += 1
                self.objects[new_id] = TrackedObject(new_id, bbox)
                det["track_id"] = new_id
                current_ids.add(new_id)
        stale = [
            oid for oid, obj in self.objects.items()
            if oid not in current_ids and obj.is_stale(self.stale_timeout)
        ]
        for oid in stale:
            del self.objects[oid]
        self.current_ids = current_ids
        return self.objects
