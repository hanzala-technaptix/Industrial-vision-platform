import math
from typing import Any, Optional


def is_valid_bbox(bbox: Any) -> bool:
    """True if bbox is four finite numbers (YOLO xyxy)."""
    if bbox is None:
        return False
    try:
        if len(bbox) != 4:
            return False
        x1, y1, x2, y2 = (float(bbox[i]) for i in range(4))
    except (TypeError, ValueError, KeyError):
        return False
    return all(math.isfinite(c) for c in (x1, y1, x2, y2))
