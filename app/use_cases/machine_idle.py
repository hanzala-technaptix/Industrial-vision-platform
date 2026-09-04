"""Use case 06 — Machine running/idle via optical flow."""
from __future__ import annotations

import argparse

import cv2
import numpy as np

from app.detectors.machine_idle import MachineIdleDetector
from app.pipeline.frame_processor import FrameProcessor
from app.rendering.overlays import draw_machine_status
from demos._paths import require_machine_video
from demos.lib.video_runner import VideoRunConfig, run_video


def _parse_roi(roi_str: str) -> np.ndarray:
    pts = [[int(x), int(y)] for x, y in (p.split(",") for p in roi_str.strip().split())]
    return np.array(pts, dtype=np.int32)


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Machine idle detection")
    ap.add_argument("--source", default=None)
    ap.add_argument("--idle-seconds", type=float, default=3.0)
    ap.add_argument("--motion-threshold", type=float, default=0.5)
    ap.add_argument("--roi", type=_parse_roi, default=None)
    ap.add_argument("--show", action="store_true", default=True)
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args(argv)

    video_path = require_machine_video(args.source)

    detector = MachineIdleDetector(
        idle_seconds=args.idle_seconds,
        motion_threshold=args.motion_threshold,
        roi_polygon=args.roi,
    )

    def _overlay(frame, result):
        out = frame.copy()
        meta = (result.detections[0].get("metadata") if result.detections else {}) or {}
        if meta.get("roi_polygon"):
            poly = np.array(meta["roi_polygon"], dtype=np.int32)
            cv2.polylines(out, [poly], True, (0, 255, 255), 2)
        return draw_machine_status(
            out,
            meta.get("state", "active"),
            float(meta.get("idle_seconds", 0)),
            float(meta.get("idle_threshold", args.idle_seconds)),
            float(meta.get("motion", 0)),
        )

    run_video(
        FrameProcessor(detectors=[detector]),
        VideoRunConfig(
            video_path=video_path,
            show=args.show,
            max_frames=args.max_frames,
            window_title="Machine Idle",
            on_frame=_overlay,
        ),
    )
    return 0
