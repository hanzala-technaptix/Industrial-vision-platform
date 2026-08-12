"""Frame annotation. PPE-aware color palette."""
from __future__ import annotations

import cv2

from app.utils.bbox import is_valid_bbox


# BGR colors (OpenCV convention)
_PALETTE = {
    "Person":         (255, 200,   0),  # cyan-ish
    "Hardhat":        (  0, 220,   0),  # green
    "NO-Hardhat":     (  0,   0, 240),  # red
    "Mask":           (  0, 200, 120),
    "NO-Mask":        (  0,  60, 240),
    "Safety Vest":    (  0, 200, 180),
    "NO-Safety Vest": (  0,  40, 240),
    "Gloves":         (200, 200,   0),
    "NO-Gloves":      ( 40,   0, 240),
    "Goggles":        (180, 180,  60),
    "NO-Goggles":     ( 40,  40, 220),
    "Fall-Detected":  (  0,   0, 255),
    "Ladder":         (140, 140, 140),
    "Safety Cone":    (  0, 165, 255),
}
_DEFAULT_COLOR = (200, 200, 200)


def _color_for(label: str) -> tuple:
    if not label:
        return _DEFAULT_COLOR
    return _PALETTE.get(label, _DEFAULT_COLOR)


def draw_detections(frame, detections, alert=None):
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

        try:
            conf = float(det.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0

        # Emphasize violations
        thickness = 3 if label.startswith("NO-") else 2

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        tid = det.get("track_id")
        text_parts = [label]
        if tid is not None:
            text_parts.append(f"#{tid}")
        text_parts.append(f"{conf:.2f}")
        text = " ".join(text_parts)

        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        pad_y = th + 8
        y_bg_top = max(0, y1 - pad_y)
        cv2.rectangle(frame, (x1, y_bg_top), (x1 + tw + 4, y1), color, -1)
        cv2.putText(frame, text, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    if alert:
        cv2.putText(frame, str(alert), (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2, cv2.LINE_AA)

    return frame
