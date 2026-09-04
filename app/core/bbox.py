"""Bounding-box helpers (xyxy convention)."""
from __future__ import annotations

import math
from typing import Any, Sequence


def is_valid_bbox(bbox: Any) -> bool:
    if bbox is None:
        return False
    try:
        if len(bbox) != 4:
            return False
        vals = [float(bbox[i]) for i in range(4)]
    except (TypeError, ValueError, KeyError):
        return False
    if not all(math.isfinite(v) for v in vals):
        return False
    x1, y1, x2, y2 = vals
    return x2 > x1 and y2 > y1


def bbox_area(bbox: Sequence[float]) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def bbox_intersection(a: Sequence[float], b: Sequence[float]) -> float:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)


def bbox_iou(a: Sequence[float], b: Sequence[float]) -> float:
    inter = bbox_intersection(a, b)
    if inter <= 0:
        return 0.0
    union = bbox_area(a) + bbox_area(b) - inter
    return inter / union if union > 0 else 0.0


def containment(inner: Sequence[float], outer: Sequence[float]) -> float:
    inter = bbox_intersection(inner, outer)
    a = bbox_area(inner)
    return inter / a if a > 0 else 0.0
