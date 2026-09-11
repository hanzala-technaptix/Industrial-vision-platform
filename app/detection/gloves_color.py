"""Fallback glove check when ppe.pt misses small nitrile/work gloves."""
from __future__ import annotations

from typing import Any, Dict, Optional

import cv2
import numpy as np


def infer_gloves(frame, person_bbox) -> Optional[Dict[str, Any]]:
    """Return Gloves / NO-Gloves from the lower person box, or None if unsure."""
    if frame is None or person_bbox is None or len(person_bbox) != 4:
        return None
    x1, y1, x2, y2 = (int(round(float(v))) for v in person_bbox)
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    ph, pw = y2 - y1, x2 - x1
    if ph < 80 or pw < 40:
        return None

    hy1 = y1 + int(ph * 0.52)
    hy2 = y1 + int(ph * 0.88)
    roi = frame[hy1:hy2, x1:x2]
    if roi.size == 0:
        return None

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    H, S, V = cv2.split(hsv)
    glove = ((H >= 95) & (H <= 130) & (S >= 90) & (V >= 50)) | (
        (H >= 125) & (H <= 170) & (S >= 50) & (V >= 40)
    )
    yellow = (H >= 16) & (H <= 40) & (S >= 90) & (V >= 80)
    glove = glove | yellow
    skin = (H <= 22) & (S >= 40) & (S <= 180) & (V >= 70) & (V <= 230)

    glove_frac = float(glove.mean())
    glove_px = int(glove.sum())
    skin_frac = float(skin.mean())

    if glove_frac >= 0.012 or glove_px >= 280:
        ys, xs = np.where(glove)
        bx1, by1 = int(xs.min()), int(ys.min())
        bx2, by2 = int(xs.max()) + 1, int(ys.max()) + 1
        conf = min(0.82, 0.38 + 2.5 * glove_frac)
        return {
            "label": "Gloves",
            "ppe_type": "gloves",
            "polarity": "positive",
            "confidence": conf,
            "bbox": [float(x1 + bx1), float(hy1 + by1), float(x1 + bx2), float(hy1 + by2)],
        }

    if skin_frac >= 0.09 and glove_frac < 0.003 and glove_px < 80:
        return {
            "label": "NO-Gloves",
            "ppe_type": "gloves",
            "polarity": "negative",
            "confidence": min(0.7, 0.4 + skin_frac),
            "bbox": [float(x1), float(hy1), float(x2), float(hy2)],
        }
    return None
