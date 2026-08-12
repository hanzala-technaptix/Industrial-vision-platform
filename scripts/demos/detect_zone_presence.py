import argparse
import sys

import cv2
import numpy as np
from ultralytics import YOLO


def parse_zone(zone_str):
    pts = []
    for pair in zone_str.strip().split():
        try:
            x, y = pair.split(',')
            pts.append([int(x), int(y)])
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"Zone points must be in 'x,y' format with spaces between pairs: {pair}"
            )
    if len(pts) < 3:
        raise argparse.ArgumentTypeError("Zone must contain at least 3 points")
    return np.array(pts, dtype=np.int32)


def point_in_polygon(point, polygon):
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def draw_overlay(frame, polygon, is_present):
    color = (0, 255, 0) if is_present else (0, 0, 255)
    overlay = frame.copy()
    cv2.fillPoly(overlay, [polygon], color)
    alpha = 0.2
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    cv2.polylines(frame, [polygon], isClosed=True, color=color, thickness=2)


def draw_status(frame, is_present):
    text = "PRESENT" if is_present else "ABSENT"
    color = (0, 255, 0) if is_present else (0, 0, 255)
    cv2.putText(
        frame,
        f"Station status: {text}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        color,
        2,
        cv2.LINE_AA,
    )


def draw_boxes(frame, boxes):
    for box in boxes:
        x1, y1, x2, y2 = map(int, box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        # Draw foot point so you can see what is being checked
        foot_x = int((x1 + x2) / 2)
        foot_y = int(y2)
        cv2.circle(frame, (foot_x, foot_y), 6, (0, 255, 255), -1)
        cv2.putText(
            frame,
            "person",
            (x1, y1 - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )


def get_default_zone(frame):
    h, w = frame.shape[:2]
    # Cover nearly full frame so any standing person is inside the zone
    return np.array(
        [
            [int(w * 0.05), int(h * 0.05)],
            [int(w * 0.95), int(h * 0.05)],
            [int(w * 0.95), int(h * 0.95)],
            [int(w * 0.05), int(h * 0.95)],
        ],
        dtype=np.int32,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Human presence detection demo using YOLOv8 person detection."
    )
    parser.add_argument(
        "--source",
        default="0",
        help="Video source: path to video file or webcam index (default=0).",
    )
    parser.add_argument(
        "--model",
        default="yolov8n.pt",
        help="YOLOv8 model file to use for detection (default=yolov8n.pt).",
    )
    parser.add_argument(
        "--zone",
        type=parse_zone,
        default=None,
        help="Station zone polygon as x,y pairs separated by spaces, e.g. '100,200 400,200 400,450 100,450'.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.35,
        help="Confidence threshold for person detections (default=0.35).",
    )
    args = parser.parse_args()

    source = 0 if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Error: Unable to open video source {args.source}")
        sys.exit(1)

    ret, frame = cap.read()
    if not ret:
        print("Error: Unable to read from source.")
        sys.exit(1)

    zone = args.zone if args.zone is not None else get_default_zone(frame)
    model = YOLO(args.model)

    print("Starting detection. Press ESC or q to quit.")
    print(f"Zone corners: {zone.tolist()}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, conf=args.threshold, classes=[0], verbose=False)
        person_boxes = []

        for r in results:
            for box in r.boxes:
                if int(box.cls[0]) != 0:
                    continue
                person_boxes.append(box.xyxy[0].cpu().numpy())

        present = False
        for box in person_boxes:
            x1, y1, x2, y2 = box
            # FIX: use foot point (bottom-center) not bounding box center
            # A standing person's center is at ~50% frame height,
            # but the default zone starts at 70% — so center check always fails.
            # Foot point is at y2 which sits inside the zone correctly.
            foot_point = ((x1 + x2) / 2, y2)
            if point_in_polygon(foot_point, zone):
                present = True
                break

        draw_overlay(frame, zone, present)
        draw_boxes(frame, person_boxes)
        draw_status(frame, present)

        cv2.imshow("Human Presence Detection", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q")):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
