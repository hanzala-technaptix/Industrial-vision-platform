import argparse
import sys
import time
import cv2
import numpy as np


def parse_roi(roi_str):
    pts = []
    for pair in roi_str.strip().split():
        try:
            x, y = pair.split(',')
            pts.append([int(x), int(y)])
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"ROI points must be in 'x,y' format with spaces between pairs: {pair}"
            )
    if len(pts) < 3:
        raise argparse.ArgumentTypeError("ROI must contain at least 3 points.")
    return np.array(pts, dtype=np.int32)


def format_time(seconds):
    return f"{int(seconds):02d}.{int((seconds - int(seconds)) * 10)}s"


def draw_status(frame, state, idle_seconds, threshold, motion_val):
    label = "RUNNING" if state == "active" else "IDLE"
    color = (0, 255, 0) if state == "active" else (0, 0, 255)

    cv2.rectangle(frame, (10, 10), (440, 110), (0, 0, 0), -1)
    cv2.rectangle(frame, (10, 10), (440, 110), color, 2)

    cv2.putText(frame, f"Status: {label}", (20, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2, cv2.LINE_AA)
    cv2.putText(frame, f"Idle timer: {format_time(idle_seconds)} / {int(threshold)}s",
                (20, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, f"Motion: {motion_val:.3f}", (20, 102),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1, cv2.LINE_AA)


def create_roi_mask(shape, polygon):
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [polygon], 255)
    return mask


def draw_motion_heatmap(frame, diff_uint8, roi_mask=None):
    diff_colored = cv2.applyColorMap(diff_uint8, cv2.COLORMAP_JET)
    overlay = frame.copy()
    combined = cv2.addWeighted(frame, 0.4, diff_colored, 0.6, 0)

    if roi_mask is None:
        mask = diff_uint8 > 15
        overlay[mask] = combined[mask]
    else:
        mask = (roi_mask > 0) & (diff_uint8 > 15)
        overlay[mask] = combined[mask]

    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)


def crop_window(frame, polygon):
    x, y, w, h = cv2.boundingRect(polygon)
    return frame[y:y+h, x:x+w], (x, y, w, h)


def main():
    parser = argparse.ArgumentParser(
        description="Machine running/idle detection using optical flow and heatmap overlay."
    )
    parser.add_argument("--source", default="0",
                        help="Video source: file path or webcam index.")
    parser.add_argument("--idle-seconds", type=float, default=10.0,
                        help="Seconds of low motion before state flips to IDLE.")
    parser.add_argument("--motion-threshold", type=float, default=0.5,
                        help="Optical flow magnitude threshold (default=0.5). Lower is more sensitive.")
    parser.add_argument("--roi", type=parse_roi, default=None,
                        help="Optional machine ROI as 'x1,y1 x2,y2 x3,y3 ...'.")
    parser.add_argument("--loop", action="store_true",
                        help="Loop video file when it ends.")
    args = parser.parse_args()

    source = 0 if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Error: Cannot open source: {args.source}")
        sys.exit(1)

    ret, frame = cap.read()
    if not ret:
        print("Error: Unable to read from source.")
        sys.exit(1)

    roi_mask = None
    roi_poly = None
    roi_box = None
    if args.roi is not None:
        roi_poly = args.roi
        roi_mask = create_roi_mask(frame.shape, roi_poly)
        _, roi_box = crop_window(frame, roi_poly)

    prev_gray = None
    idle_start = None
    idle_duration = 0.0
    state = "active"

    motion_history = []
    HISTORY_LEN = 8

    cv2.namedWindow("Machine Running / Idle Detection", cv2.WINDOW_NORMAL)

    while True:
        ret, frame = cap.read()
        if not ret:
            if args.loop:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                prev_gray = None
                continue
            break

        display = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 0)

        if roi_mask is not None:
            x, y, w, h = roi_box
            gray_crop = gray[y:y+h, x:x+w]
            mask_crop = roi_mask[y:y+h, x:x+w]
            prev_crop = prev_gray[y:y+h, x:x+w] if prev_gray is not None else None
        else:
            gray_crop = gray
            mask_crop = None
            prev_crop = prev_gray

        motion_score = 0.0
        if prev_crop is not None and gray_crop.shape == prev_crop.shape and gray_crop.size > 0:
            flow = cv2.calcOpticalFlowFarneback(
                prev_crop,
                gray_crop,
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
            if mask_crop is not None:
                valid = mask_crop > 0
                if np.count_nonzero(valid) > 0:
                    motion_score = float(np.sum(mag[valid]) / np.count_nonzero(valid))
                else:
                    motion_score = 0.0
                mag[~valid] = 0
            else:
                motion_score = float(np.mean(mag))

            mag_uint8 = np.zeros_like(mag, dtype=np.uint8)
            cv2.normalize(mag, mag_uint8, 0, 255, cv2.NORM_MINMAX)

            if roi_mask is not None:
                diff_full = np.zeros_like(gray, dtype=np.uint8)
                diff_full[y:y+h, x:x+w] = mag_uint8
                draw_motion_heatmap(display, diff_full, roi_mask)
                cv2.polylines(display, [roi_poly], True, (0, 255, 255), 2)
            else:
                draw_motion_heatmap(display, mag_uint8)
        else:
            if roi_mask is not None:
                cv2.polylines(display, [roi_poly], True, (0, 255, 255), 2)

        motion_history.append(motion_score)
        if len(motion_history) > HISTORY_LEN:
            motion_history.pop(0)
        smoothed_motion = float(np.mean(motion_history))

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
            cv2.rectangle(flash, (0, 0), (display.shape[1], display.shape[0]), (0, 0, 255), 8)
            cv2.addWeighted(flash, 0.4, display, 0.6, 0, display)

        cv2.imshow("Machine Running / Idle Detection", display)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q")):
            break

        prev_gray = gray

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
