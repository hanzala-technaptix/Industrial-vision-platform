import cv2

from app.utils.bbox import is_valid_bbox


def _display_label(label) -> str:
    """Uppercase display label; map synonyms to MASK / NO_MASK for coloring."""
    s = str(label or "").strip().upper().replace("-", "_")
    if s == "MASK":
        return "MASK"
    if s in ("NO_MASK", "NOMASK", "PERSON", "FACE"):
        return "NO_MASK"
    if "MASK" in s and s != "MASK":
        return "NO_MASK"
    return s or "UNKNOWN"


def draw_detections(frame, detections, alert=None):
    """
    Visualization only: draw boxes for valid bbox rows. Never raises on bad input.
    """
    if frame is None:
        return None

    if not detections:
        return frame

    for det in detections:
        if not isinstance(det, dict):
            continue

        bbox = det.get("bbox", None)
        if not is_valid_bbox(bbox):
            continue

        try:
            x1, y1, x2, y2 = (int(round(float(bbox[i]))) for i in range(4))
        except (TypeError, ValueError):
            continue

        disp = _display_label(det.get("label"))
        if disp == "MASK":
            color = (0, 255, 0)
        elif disp == "NO_MASK":
            color = (0, 0, 255)
        else:
            color = (0, 255, 255)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        try:
            conf = float(det.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        text = f"{disp} {conf:.2f}"
        (w, h), _ = cv2.getTextSize(
            text,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            1,
        )
        pad_y = max(25, h + 10)
        cv2.rectangle(frame, (x1, y1 - pad_y), (x1 + w, y1), color, -1)
        cv2.putText(
            frame,
            text,
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
        )

    if alert:
        cv2.putText(
            frame,
            str(alert),
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 0, 255),
            3,
        )

    return frame
