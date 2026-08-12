"""PPEDetector — Phase 1 core.

Runs the ppe_yolov8_best.pt model, tracks Person boxes, associates PPE
detections with tracked persons, and produces enriched DetectionResults
carrying per-person compliance metadata for the EventEngine to consume.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import (
    DEVICE,
    PPE_ASSOC_MIN_OVERLAP,
    PPE_CLASS_MAP,
    PPE_CONF_THRESHOLD,
    PPE_FALLBACK_PATH,
    PPE_INFER_IMGSZ,
    PPE_IOU_THRESHOLD,
    PPE_MODEL_PATH,
    PPE_REQUIRED_ITEMS,
    TRACK_DISTANCE_THRESHOLD,
    TRACK_STALE_TIMEOUT,
)
from app.pipeline.base_detector import BaseDetector, DetectionResult
from app.tracking.tracker import ObjectTracker
from app.utils.bbox import bbox_iou, containment, is_valid_bbox


# Compliance state literals
STATE_COMPLIANT = "compliant"
STATE_VIOLATING = "violating"
STATE_UNKNOWN = "unknown"


class PPEDetector(BaseDetector):
    name = "ppe"
    frame_stride = 1

    def __init__(self, camera_id: str = "cam"):
        super().__init__(camera_id)
        self.model = None
        self.tracker = ObjectTracker(
            distance_threshold=TRACK_DISTANCE_THRESHOLD,
            stale_timeout=TRACK_STALE_TIMEOUT,
        )
        self.required_items = [i.strip().lower() for i in PPE_REQUIRED_ITEMS if i.strip()]
        # Per-track compliance history: {track_id: {ppe_type: state}}
        self._per_track_state: Dict[int, Dict[str, str]] = {}

    def setup(self) -> None:
        from ultralytics import YOLO
        path = PPE_MODEL_PATH if PPE_MODEL_PATH.exists() else PPE_FALLBACK_PATH
        if not path.exists():
            print(f"[ppe] no local weights; downloading yolov8n")
            self.model = YOLO("yolov8n.pt")
        else:
            print(f"[ppe] loading {path}")
            self.model = YOLO(str(path))
        try:
            self.model.to(DEVICE)
        except Exception:
            pass
        # Warm-up inference gets the first-call compile cost out of the way
        try:
            import numpy as np
            _dummy = np.zeros((320, 320, 3), dtype="uint8")
            self.model(_dummy, verbose=False)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def _infer(self, frame) -> List[Dict[str, Any]]:
        if self.model is None:
            return []
        try:
            results = self.model(
                frame,
                conf=PPE_CONF_THRESHOLD,
                iou=PPE_IOU_THRESHOLD,
                imgsz=PPE_INFER_IMGSZ,
                verbose=False,
            )
        except Exception as e:
            print(f"[ppe] inference error: {e}")
            return []

        out: List[Dict[str, Any]] = []
        for r in results:
            if r.boxes is None or len(r.boxes) == 0:
                continue
            for box in r.boxes:
                try:
                    cls_id = int(box.cls[0].item())
                    label = self.model.names.get(cls_id) if isinstance(self.model.names, dict) else self.model.names[cls_id]
                    conf = float(box.conf[0].item())
                    xyxy = [float(v) for v in box.xyxy[0].tolist()]
                except Exception:
                    continue
                if not is_valid_bbox(xyxy):
                    continue
                out.append({"label": str(label), "confidence": conf, "bbox": xyxy})
        return out

    # ------------------------------------------------------------------
    # Association: person ↔ PPE
    # ------------------------------------------------------------------
    def _split_and_map(self, raw: List[Dict[str, Any]]):
        """Split raw detections into person list and ppe list, with normalized types."""
        persons: List[Dict[str, Any]] = []
        ppe_items: List[Dict[str, Any]] = []
        misc: List[Dict[str, Any]] = []  # things we still want to render but don't feed into compliance
        for det in raw:
            label = det["label"]
            mapping = PPE_CLASS_MAP.get(label)
            if mapping is None:
                misc.append(det)
                continue
            ppe_type, polarity = mapping
            det["ppe_type"] = ppe_type
            det["polarity"] = polarity  # "person" | "positive" | "negative" | ...
            if polarity == "person":
                persons.append(det)
            elif polarity in ("positive", "negative"):
                ppe_items.append(det)
            else:
                misc.append(det)
        return persons, ppe_items, misc

    def _associate(self, persons: List[Dict[str, Any]], ppe_items: List[Dict[str, Any]]):
        """For each person, pick the best-matching PPE item per (ppe_type, polarity).

        A PPE box is a candidate for a person if `containment(ppe, person) >= threshold`.
        Best match = highest containment × confidence.
        """
        # Init per-person compliance dict
        for p in persons:
            p["ppe_status"] = {
                t: {"state": STATE_UNKNOWN, "best_conf": 0.0, "source_bbox": None}
                for t in self.required_items
            }
            p["_associated_ppe"] = []

        for item in ppe_items:
            best_p = None
            best_score = 0.0
            best_containment = 0.0
            for p in persons:
                c = containment(item["bbox"], p["bbox"])
                if c < PPE_ASSOC_MIN_OVERLAP:
                    continue
                score = c * (item.get("confidence") or 0.0)
                if score > best_score:
                    best_score = score
                    best_p = p
                    best_containment = c
            if best_p is None:
                continue
            item["assoc_person_track_id"] = best_p.get("track_id")
            item["assoc_containment"] = best_containment
            best_p["_associated_ppe"].append(item)

            ppe_type = item["ppe_type"]
            if ppe_type not in best_p["ppe_status"]:
                continue
            polarity = item["polarity"]
            slot = best_p["ppe_status"][ppe_type]
            if polarity == "positive":
                # Positive wins over unknown; a strong positive beats a weak negative
                if slot["state"] == STATE_UNKNOWN or (
                    slot["state"] == STATE_VIOLATING and item["confidence"] > slot["best_conf"]
                ):
                    slot["state"] = STATE_COMPLIANT
                    slot["best_conf"] = item["confidence"]
                    slot["source_bbox"] = item["bbox"]
            elif polarity == "negative":
                if slot["state"] == STATE_UNKNOWN or (
                    slot["state"] == STATE_COMPLIANT and item["confidence"] > slot["best_conf"]
                ):
                    slot["state"] = STATE_VIOLATING
                    slot["best_conf"] = item["confidence"]
                    slot["source_bbox"] = item["bbox"]

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        raw = self._infer(frame)
        if not raw:
            self.tracker.update([])  # advance staleness
            return []

        persons, ppe_items, misc = self._split_and_map(raw)

        # Track only person boxes
        self.tracker.update(persons)  # assigns track_id in-place

        # Associate PPE items to tracked persons
        self._associate(persons, ppe_items)

        # Update per-track history + attach violation summary to each person
        for p in persons:
            tid = p.get("track_id")
            if tid is None:
                continue
            hist = self._per_track_state.setdefault(tid, {})
            violations: List[str] = []
            compliant: List[str] = []
            unknown: List[str] = []
            for ppe_type, slot in p["ppe_status"].items():
                state = slot["state"]
                hist[ppe_type] = state
                if state == STATE_VIOLATING:
                    violations.append(ppe_type)
                elif state == STATE_COMPLIANT:
                    compliant.append(ppe_type)
                else:
                    unknown.append(ppe_type)
            p["metadata"] = {
                "role": "person",
                "compliant": compliant,
                "violating": violations,
                "unknown": unknown,
                "compliance_ratio": len(compliant) / max(1, len(self.required_items)),
            }

        # Prune history for tracks that no longer exist
        live = set(self.tracker.objects.keys())
        for gone in [t for t in self._per_track_state if t not in live]:
            del self._per_track_state[gone]

        # Build DetectionResult list — persons + PPE items + misc — all rendered
        out: List[DetectionResult] = []
        for p in persons:
            out.append({
                "detector": self.name,
                "label": "Person",
                "confidence": p["confidence"],
                "bbox": p["bbox"],
                "track_id": p.get("track_id"),
                "metadata": p["metadata"],
            })
        for item in ppe_items:
            out.append({
                "detector": self.name,
                "label": item["label"],
                "confidence": item["confidence"],
                "bbox": item["bbox"],
                "track_id": item.get("assoc_person_track_id"),
                "metadata": {
                    "role": "ppe_item",
                    "ppe_type": item["ppe_type"],
                    "polarity": item["polarity"],
                    "assoc_containment": round(item.get("assoc_containment", 0.0), 3),
                },
            })
        for m in misc:
            out.append({
                "detector": self.name,
                "label": m["label"],
                "confidence": m["confidence"],
                "bbox": m["bbox"],
                "metadata": {"role": "misc"},
            })

        return out

    def get_state(self) -> Dict[str, Any]:
        # Per-track compliance snapshot for the API/dashboard
        tracked: List[Dict[str, Any]] = []
        for tid, obj in self.tracker.objects.items():
            hist = self._per_track_state.get(tid, {})
            tracked.append({
                "track_id": tid,
                "bbox": obj.bbox,
                "compliance": hist,
                "violating": [k for k, v in hist.items() if v == STATE_VIOLATING],
            })
        return {
            "detector": self.name,
            "enabled": self.enabled,
            "conf_threshold": PPE_CONF_THRESHOLD,
            "required_items": self.required_items,
            "tracked_persons": len(tracked),
            "persons": tracked,
        }
