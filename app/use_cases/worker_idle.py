"""Use case 07 — Worker active/idle/absent."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from app.detectors.worker_idle import WorkerIdleDetector
from app.pipeline.frame_processor import FrameProcessor
from demos._paths import DEFAULT_VIDEOS, DEFAULT_YOLO
from demos.lib.video_runner import VideoRunConfig, run_video


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Worker idle detection")
    ap.add_argument("--source", default=str(DEFAULT_VIDEOS["worker_idle"]))
    ap.add_argument("--idle-seconds", type=float, default=8.0)
    ap.add_argument("--motion-threshold", type=float, default=0.003)
    ap.add_argument("--model", default=str(DEFAULT_YOLO))
    ap.add_argument("--threshold", type=float, default=0.35)
    ap.add_argument("--show", action="store_true", default=True)
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args(argv)

    src = args.source
    video_path = Path(src).resolve() if not str(src).isdigit() else None
    if video_path is not None and not video_path.exists():
        print(f"Error: video not found: {video_path}")
        return 1

    detector = WorkerIdleDetector(
        idle_seconds=args.idle_seconds,
        motion_threshold=args.motion_threshold,
        person_conf=args.threshold,
        model_path=Path(args.model),
    )

    def _overlay(frame, result):
        out = result.annotated
        meta = (result.detections[0].get("metadata") if result.detections else {}) or {}
        state = meta.get("state", "absent")
        if state == "absent":
            color = (0, 0, 255); label = "ABSENT"
        elif state == "active":
            color = (0, 255, 0); label = "ACTIVE"
        else:
            color = (0, 255, 255); label = "IDLE"
        cv2.rectangle(out, (10, 10), (540, 110), (0, 0, 0), -1)
        cv2.rectangle(out, (10, 10), (540, 110), color, 2)
        cv2.putText(out, f"Worker: {label}", (20, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
        if state != "absent":
            cv2.putText(
                out,
                f"Idle: {meta.get('idle_seconds', 0):.1f}s / {int(meta.get('idle_threshold', args.idle_seconds))}s"
                f"  motion={meta.get('motion', 0):.3f}",
                (20, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2,
            )
        return out

    if video_path is not None:
        run_video(
            FrameProcessor(detectors=[detector]),
            VideoRunConfig(
                video_path=video_path,
                show=args.show,
                max_frames=args.max_frames,
                window_title="Worker Idle",
                on_frame=_overlay,
            ),
        )
    else:
        # Webcam mode (int source) — bypass file-based runner
        _run_webcam(detector, int(src), _overlay, args)
    return 0


def _run_webcam(detector, index: int, on_frame, args) -> None:
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"Cannot open webcam {index}")
        return
    detector.setup()
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        n += 1
        rows = detector.process(frame, n)
        from app.rendering.renderer import render_frame
        annotated = render_frame(frame, rows)
        from app.pipeline.result import FrameResult
        annotated = on_frame(frame, FrameResult(detections=rows, annotated=annotated, frame_no=n))
        cv2.imshow("Worker Idle", annotated)
        if (cv2.waitKey(1) & 0xFF) in (27, ord("q")):
            break
        if args.max_frames and n >= args.max_frames:
            break
    cap.release()
    cv2.destroyAllWindows()
    detector.cleanup()
