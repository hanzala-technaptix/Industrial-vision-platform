import argparse
import sys
import time
import cv2
import numpy as np
from ultralytics import YOLO


def format_time(seconds):
    return f"{int(seconds):02d}.{int((seconds - int(seconds)) * 10)}s"


def draw_status(frame, state, idle_seconds, threshold, motion_val):
    if state == "absent":
        label = "ABSENT"
        color = (0, 0, 255)
    else:
        label = "ACTIVE" if state == "active" else "IDLE"
        color = (0, 255, 0) if state == "active" else (0, 255, 255)

    cv2.rectangle(frame, (10, 10), (540, 110), (0, 0, 0), -1)
    cv2.rectangle(frame, (10, 10), (540, 110), color, 2)

    cv2.putText(frame, f"Worker: {label}", (20, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2, cv2.LINE_AA)
    if state != "absent":
        cv2.putText(frame, f"Idle timer: {format_time(idle_seconds)} / {int(threshold)}s",
                    (20, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"Motion: {motion_val:.3f}", (20, 102),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1, cv2.LINE_AA)
    else:
        cv2.putText(frame, "No person detected", (20, 78),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)


def draw_motion_heatmap(frame, diff_uint8, mask=None):
    diff_colored = cv2.applyColorMap(diff_uint8, cv2.COLORMAP_JET)
    overlay = frame.copy()
    combined = cv2.addWeighted(frame, 0.4, diff_colored, 0.6, 0)

    if mask is None:
        mask_area = diff_uint8 > 15
    else:
        mask_area = (mask > 0) & (diff_uint8 > 15)

    overlay[mask_area] = combined[mask_area]
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)


def get_person_roi(frame, model, threshold=0.35):
    results = model(frame, conf=threshold, classes=[0], verbose=False)
    best_box = None
    best_conf = 0.0
    for r in results:
        for box in r.boxes:
            conf = float(box.conf[0])
            if conf > best_conf:
                best_conf = conf
                best_box = box.xyxy[0].cpu().numpy()
    return best_box


def main():
    parser = argparse.ArgumentParser(
        description="Human active/idle detection using YOLO person detection + optical flow."
    )
    parser.add_argument("--source", default="0",
                        help="Video source: file path or webcam index.")
    parser.add_argument("--idle-seconds", type=float, default=10.0,
                        help="Seconds of low motion before idle state triggers.")
    parser.add_argument("--motion-threshold", type=float, default=0.003,
                        help="Motion threshold for person ROI; lower values are more sensitive.")
    parser.add_argument("--model", default="yolov8n.pt",
                        help="YOLOv8 model file to use for person detection.")
    parser.add_argument("--threshold", type=float, default=0.35,
                        help="YOLO confidence threshold for person detections.")
    args = parser.parse_args()

    source = 0 if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Error: Cannot open source: {args.source}")
        sys.exit(1)

    model = YOLO(args.model)
    print("Loading YOLO model...")
    print("Starting human idle detection. Press ESC or q to quit.")

    prev_gray = None
    idle_start = None
    idle_duration = 0.0
    state = "absent"

    motion_history = []
    HISTORY_LEN = 8

    frame_count = 0
    person_box = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 0)

        if frame_count % 10 == 0:
            person_box = get_person_roi(frame, model, threshold=args.threshold)

        if person_box is not None:
            x1, y1, x2, y2 = map(int, person_box)
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(display, "person", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            roi_gray = gray[y1:y2, x1:x2]
            roi_prev = prev_gray[y1:y2, x1:x2] if prev_gray is not None else None
        else:
            roi_gray = None
            roi_prev = None

        motion_score = 0.0
        if roi_prev is not None and roi_gray.shape == roi_prev.shape and roi_gray.size > 0:
            flow = cv2.calcOpticalFlowFarneback(
                roi_prev,
                roi_gray,
                None,
                pyr_scale=0.5,
                levels=3,
                winsize=15,
                iterations=3,
                poly_n=5,
                poly_sigma=1.2,
                flags=0,
            )
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            motion_score = float(np.mean(mag))

            mag_uint8 = np.zeros_like(mag, dtype=np.uint8)
            cv2.normalize(mag, mag_uint8, 0, 255, cv2.NORM_MINMAX)
            diff_full = np.zeros_like(gray, dtype=np.uint8)
            diff_full[y1:y2, x1:x2] = mag_uint8
            draw_motion_heatmap(display, diff_full, mask=(diff_full > 0))

        motion_history.append(motion_score)
        if len(motion_history) > HISTORY_LEN:
            motion_history.pop(0)
        smoothed_motion = float(np.mean(motion_history))

        if person_box is None:
            state = "absent"
            idle_start = None
            idle_duration = 0.0
        else:
            if smoothed_motion < args.motion_threshold:
                if idle_start is None:
                    idle_start = time.time()
                idle_duration = time.time() - idle_start
            else:
                idle_start = None
                idle_duration = 0.0
            state = "idle" if idle_duration >= args.idle_seconds else "active"

        draw_status(display, state, idle_duration, args.idle_seconds, smoothed_motion)

        if state == "idle":
            flash = display.copy()
            cv2.rectangle(flash, (0, 0), (display.shape[1], display.shape[0]), (0, 255, 255), 8)
            cv2.addWeighted(flash, 0.4, display, 0.6, 0, display)

        cv2.imshow("Human Active / Idle Detection", display)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q")):
            break

        prev_gray = gray
        frame_count += 1

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
