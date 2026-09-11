"""PPEDetector — Phase 1 core.

Runs models/ppe.pt, tracks Person boxes, associates PPE
detections with tracked persons, and produces enriched DetectionResults
carrying per-person compliance metadata for the EventEngine to consume.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.config import (
    ACTIVE_PPE_CLASSES,
    DEVICE,
    MASK_ASSOC_MIN_OVERLAP,
    MASK_CONF_THRESHOLD,
    MASK_INFER_IMGSZ,
    MASK_MODEL_PATH,
    PERSON_CONF_THRESHOLD,
    PERSON_INFER_IMGSZ,
    PERSON_MODEL_PATH,
    PPE_ASSOC_MIN_OVERLAP,
    PPE_CLASS_MAP,
    PPE_CONF_THRESHOLD,
    PPE_FALLBACK_PATH,
    PPE_INFER_IMGSZ,
    PPE_IOU_THRESHOLD,
    PPE_MODEL_PATH,
    PPE_POSITIVE_MIN_CONF,
    PPE_REQUIRED_ITEMS,
    TRACK_DISTANCE_THRESHOLD,
    TRACK_STALE_TIMEOUT,
)
from app.core.bbox import containment, is_valid_bbox, nms_detections
from app.detection.base import BaseDetector, DetectionResult
from app.detection.gloves_color import infer_gloves
from app.tracking.tracker import ObjectTracker


# Compliance state literals
STATE_COMPLIANT = "compliant"
STATE_VIOLATING = "violating"
STATE_UNKNOWN = "unknown"

# Dedicated mask.pt uses mask/no_mask; ppe.pt uses Mask/NO-Mask.
_LABEL_CANON = {
    "person": "Person",
    "hardhat": "Hardhat",
    "no-hardhat": "NO-Hardhat",
    "no_hardhat": "NO-Hardhat",
    "mask": "Mask",
    "no-mask": "NO-Mask",
    "no_mask": "NO-Mask",
    "safety vest": "Safety Vest",
    "safety_vest": "Safety Vest",
    "safety-vest": "Safety Vest",
    "no-safety vest": "NO-Safety Vest",
    "no_safety_vest": "NO-Safety Vest",
    "no-safety-vest": "NO-Safety Vest",
    "gloves": "Gloves",
    "glove": "Gloves",
    "no-gloves": "NO-Gloves",
    "no_gloves": "NO-Gloves",
    "no-glove": "NO-Gloves",
}


def _canonical_label(label: str) -> str:
    raw = str(label).strip()
    key = raw.lower().replace("_", "-")
    return (
        _LABEL_CANON.get(raw.lower())
        or _LABEL_CANON.get(key)
        or raw
    )


class PPEDetector(BaseDetector):
    name = "ppe"
    frame_stride = 1

    def __init__(self, camera_id: str = "cam"):
        super().__init__(camera_id)
        self.ppe_model = None
        self.person_model = None
        self.mask_model = None
        self.tracker = ObjectTracker(
            distance_threshold=max(TRACK_DISTANCE_THRESHOLD, 180.0),
            stale_timeout=min(TRACK_STALE_TIMEOUT, 0.8),
        )
        self.required_items = [i.strip().lower() for i in PPE_REQUIRED_ITEMS if i.strip()]
        # Per-track compliance history: {track_id: {ppe_type: state}}
        self._per_track_state: Dict[int, Dict[str, str]] = {}
        self._visible_ids: set = set()

    def setup(self) -> None:
        from ultralytics import YOLO

        # PPE model — for equipment classes only
        ppe_path = PPE_MODEL_PATH if PPE_MODEL_PATH.exists() else PPE_FALLBACK_PATH
        if not ppe_path.exists():
            print("[ppe] no local PPE weights; downloading yolov8n as fallback")
            self.ppe_model = YOLO("yolov8n.pt")
        else:
            print(f"[ppe] loading PPE model {ppe_path}")
            self.ppe_model = YOLO(str(ppe_path))

        # Person model — COCO-trained yolov8n, reliable Person class
        person_path = PERSON_MODEL_PATH
        if not person_path.exists():
            print("[ppe] no local person weights; downloading yolov8n")
            self.person_model = YOLO("yolov8n.pt")
        else:
            print(f"[ppe] loading Person model {person_path}")
            self.person_model = YOLO(str(person_path))

        if MASK_MODEL_PATH.exists():
            print(f"[ppe] loading Mask model {MASK_MODEL_PATH}")
            self.mask_model = YOLO(str(MASK_MODEL_PATH))
        else:
            print("[ppe] no dedicated mask model — mask recall may be poor")

        for m in (self.ppe_model, self.person_model, self.mask_model):
            if m is None:
                continue
            try:
                m.to(DEVICE)
            except Exception:
                pass

        # Warm-up
        try:
            import numpy as np
            _dummy = np.zeros((320, 320, 3), dtype="uint8")
            self.ppe_model(_dummy, verbose=False)
            self.person_model(_dummy, verbose=False, classes=[0])
            if self.mask_model is not None:
                self.mask_model(_dummy, verbose=False)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def _boxes_to_dicts(self, results, model, allowed_labels=None) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for r in results:
            if r.boxes is None or len(r.boxes) == 0:
                continue
            for box in r.boxes:
                try:
                    cls_id = int(box.cls[0].item())
                    names = model.names
                    label = names.get(cls_id) if isinstance(names, dict) else names[cls_id]
                    label = _canonical_label(label)
                    conf = float(box.conf[0].item())
                    xyxy = [float(v) for v in box.xyxy[0].tolist()]
                except Exception:
                    continue
                if not is_valid_bbox(xyxy):
                    continue
                if allowed_labels is not None:
                    allowed = {_canonical_label(x) for x in allowed_labels}
                    if label not in allowed:
                        continue
                out.append({"label": str(label), "confidence": conf, "bbox": xyxy})
        return out

    def _infer(self, frame) -> List[Dict[str, Any]]:
        if self.ppe_model is None:
            return []
        combined: List[Dict[str, Any]] = []

        # 1. Person detections from COCO model — class 0 is Person; rename so
        #    downstream mapping treats it identically to the PPE model's Person.
        if self.person_model is not None:
            try:
                pr = self.person_model(
                    frame,
                    conf=max(PERSON_CONF_THRESHOLD, 0.25),
                    iou=0.45,
                    imgsz=PERSON_INFER_IMGSZ,
                    verbose=False,
                    classes=[0],
                )
                persons = self._boxes_to_dicts(pr, self.person_model)
                h, w = frame.shape[:2]
                min_h = 0.22 * h
                min_area = 0.02 * w * h
                for p in persons:
                    p["label"] = "Person"
                persons = [
                    p for p in persons
                    if (p["bbox"][3] - p["bbox"][1]) >= min_h
                    and (p["bbox"][2] - p["bbox"][0]) * (p["bbox"][3] - p["bbox"][1]) >= min_area
                ]
                combined.extend(nms_detections(persons, iou_thresh=0.4, contain_thresh=0.6))
            except Exception as e:
                print(f"[ppe] person inference error: {e}")

        # 2. PPE equipment detections — drop the PPE model's Person class
        #    (unreliable) so only equipment classes flow through.
        try:
            pr = self.ppe_model(
                frame,
                conf=PPE_CONF_THRESHOLD,
                iou=PPE_IOU_THRESHOLD,
                imgsz=PPE_INFER_IMGSZ,
                verbose=False,
            )
            items = self._boxes_to_dicts(pr, self.ppe_model)
            # Person boxes come from person.pt. Keep Mask/NO-Mask from ppe.pt even
            # when mask.pt is loaded — construction-site shots are not face crops.
            items = [i for i in items if i["label"] != "Person"]
            combined.extend(items)
        except Exception as e:
            print(f"[ppe] ppe inference error: {e}")

        # 3. Dedicated face-mask model (Person + Mask) — take Mask class only
        if self.mask_model is not None:
            try:
                mr = self.mask_model(
                    frame,
                    conf=MASK_CONF_THRESHOLD,
                    imgsz=MASK_INFER_IMGSZ,
                    verbose=False,
                )
                masks = self._boxes_to_dicts(
                    mr, self.mask_model, allowed_labels={"Mask", "NO-Mask"}
                )
                combined.extend(masks)
            except Exception as e:
                print(f"[ppe] mask inference error: {e}")

        return combined

    # ------------------------------------------------------------------
    # Association: person ↔ PPE
    # ------------------------------------------------------------------
    def _split_and_map(self, raw: List[Dict[str, Any]]):
        """Split raw detections into person list and active PPE list, with normalized types.

        The trained YOLO model may still emit Goggles / NO-Goggles / other non-Phase-1
        classes, but the application intentionally ignores them for compliance.
        """
        persons: List[Dict[str, Any]] = []
        ppe_items: List[Dict[str, Any]] = []
        misc: List[Dict[str, Any]] = []  # things we still want to render but don't feed into compliance
        for det in raw:
            label = det["label"]

            # Keep Person as the tracked entity, but ignore any non-Phase-1 PPE class.
            if label == "Person":
                mapping = PPE_CLASS_MAP.get(label)
            elif label in ACTIVE_PPE_CLASSES:
                mapping = PPE_CLASS_MAP.get(label)
            else:
                mapping = None

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
            ppe_type = item.get("ppe_type")
            if ppe_type == "mask":
                min_overlap = MASK_ASSOC_MIN_OVERLAP
            elif ppe_type == "gloves":
                min_overlap = min(PPE_ASSOC_MIN_OVERLAP, 0.12)
            else:
                min_overlap = PPE_ASSOC_MIN_OVERLAP
            for p in persons:
                c = containment(item["bbox"], p["bbox"])
                if c < min_overlap:
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
            conf = float(item.get("confidence") or 0.0)
            if polarity == "positive":
                if conf < PPE_POSITIVE_MIN_CONF:
                    continue
                if slot["state"] == STATE_UNKNOWN or (
                    slot["state"] == STATE_VIOLATING and conf > slot["best_conf"]
                ):
                    slot["state"] = STATE_COMPLIANT
                    slot["best_conf"] = conf
                    slot["source_bbox"] = item["bbox"]
            elif polarity == "negative":
                if conf < PPE_POSITIVE_MIN_CONF:
                    continue
                if slot["state"] == STATE_UNKNOWN or (
                    slot["state"] == STATE_COMPLIANT and conf > slot["best_conf"]
                ):
                    slot["state"] = STATE_VIOLATING
                    slot["best_conf"] = conf
                    slot["source_bbox"] = item["bbox"]

    def _fill_gloves(self, frame, persons: List[Dict[str, Any]], ppe_items: List[Dict[str, Any]]) -> None:
        """ppe.pt rarely fires on small nitrile gloves — fill unknown slots from color."""
        if "gloves" not in self.required_items:
            return
        for p in persons:
            slot = (p.get("ppe_status") or {}).get("gloves")
            if not slot or slot["state"] != STATE_UNKNOWN:
                continue
            hit = infer_gloves(frame, p.get("bbox"))
            if not hit:
                continue
            hit["assoc_person_track_id"] = p.get("track_id")
            hit["assoc_containment"] = 1.0
            p.setdefault("_associated_ppe", []).append(hit)
            ppe_items.append(hit)
            slot["state"] = STATE_COMPLIANT if hit["polarity"] == "positive" else STATE_VIOLATING
            slot["best_conf"] = float(hit["confidence"])
            slot["source_bbox"] = hit["bbox"]

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        raw = self._infer(frame)
        if not raw:
            self.tracker.update([])  # advance staleness
            self._visible_ids = set()
            return []

        persons, ppe_items, misc = self._split_and_map(raw)
        persons = nms_detections(persons, iou_thresh=0.4, contain_thresh=0.6)

        # Track only person boxes
        self.tracker.update(persons)  # assigns track_id in-place

        # Associate PPE items to tracked persons
        self._associate(persons, ppe_items)
        self._fill_gloves(frame, persons, ppe_items)

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
                if ppe_type == "gloves" and state == STATE_UNKNOWN:
                    prev = hist.get("gloves")
                    if prev in (STATE_COMPLIANT, STATE_VIOLATING):
                        state = prev
                        slot["state"] = prev
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
        live = set(p.get("track_id") for p in persons if p.get("track_id") is not None)
        self._visible_ids = live
        for gone in [t for t in self._per_track_state if t not in live and t not in self.tracker.objects]:
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
        visible = getattr(self, "_visible_ids", set())
        for tid, obj in self.tracker.objects.items():
            if tid not in visible:
                continue
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