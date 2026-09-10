"""Detection box drawing and PPE labels."""
from __future__ import annotations

import cv2

from app.core.bbox import is_valid_bbox

_PALETTE = {
    "Person": (255, 200, 0),
    "person": (255, 200, 0),
    "Hardhat": (0, 220, 0),
    "NO-Hardhat": (0, 0, 240),
    "Mask": (0, 200, 120),
    "NO-Mask": (0, 60, 240),
    "Safety Vest": (0, 200, 180),
    "NO-Safety Vest": (0, 40, 240),
    "Gloves": (200, 200, 0),
    "NO-Gloves": (40, 0, 240),
    "Goggles": (180, 180, 60),
    "NO-Goggles": (40, 40, 220),
    "Fall-Detected": (0, 0, 255),
    "Ladder": (140, 140, 140),
    "Safety Cone": (0, 165, 255),
}
_DEFAULT_COLOR = (200, 200, 200)

_PPE_DISPLAY = {
    "hardhat": "HARDHAT",
    "mask": "MASK",
    "vest": "VEST",
    "gloves": "GLOVES",
}


def ppe_display_name(ppe_type: str) -> str:
    return _PPE_DISPLAY.get(ppe_type.lower(), ppe_type.upper())


def _color_for(label: str) -> tuple:
    if not label:
        return _DEFAULT_COLOR
    return _PALETTE.get(label, _DEFAULT_COLOR)


def draw_detections(frame, detections):
    if frame is None:
        return None
    if not detections:
        return frame

    for det in detections:
        if not isinstance(det, dict):
            continue
        bbox = det.get("bbox")
        if not is_valid_bbox(bbox):
            continue
        try:
            x1, y1, x2, y2 = (int(round(float(bbox[i]))) for i in range(4))
        except (TypeError, ValueError):
            continue

        label = str(det.get("label") or "").strip() or "UNKNOWN"
        color = _color_for(label)
        meta = det.get("metadata") or {}

        try:
            conf = float(det.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0

        thickness = 3 if label.startswith("NO-") else 2
        if label == "Person" and meta.get("role") == "person":
            if meta.get("violating") or meta.get("alert_removed"):
                color = (0, 0, 255)
                thickness = 4

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        tid = det.get("track_id")
        text_parts = [label]
        if tid is not None:
            text_parts.append(f"#{tid}")
        text_parts.append(f"{conf:.2f}")
        if label == "Person" and meta.get("role") == "person":
            violating = meta.get("violating") or []
            compliant = meta.get("compliant") or []
            unknown = meta.get("unknown") or []
            if violating:
                text_parts.append("MISSING:" + ",".join(violating))
            if unknown:
                text_parts.append("UNKNOWN:" + ",".join(unknown))
            if compliant and not violating:
                text_parts.append("OK:" + ",".join(compliant))
        text = " ".join(text_parts)

        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        pad_y = th + 8
        y_bg_top = max(0, y1 - pad_y)
        cv2.rectangle(frame, (x1, y_bg_top), (x1 + tw + 4, y1), color, -1)
        cv2.putText(
            frame, text, (x1 + 2, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA,
        )

    return frame
