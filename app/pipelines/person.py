"""Use case 02 — Person detection (COCO class 0 only)."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from app.detection.person import PersonDetector
from app.pipeline.frame_processor import FrameProcessor
from app.core.videos import DEFAULT_VIDEOS, PERSON_MODEL
from demos.lib.video_runner import VideoRunConfig, run_video


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Person detection")
    ap.add_argument("--source", default=str(DEFAULT_VIDEOS["person"]))
    ap.add_argument("--model", default=str(PERSON_MODEL))
    ap.add_argument("--conf", type=float, default=None)
    ap.add_argument("--show", action="store_true", default=True)
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args(argv)

    video_path = Path(args.source).resolve()
    if not video_path.exists():
        print(f"Error: Cannot open {args.source}")
        return 1

    detector = PersonDetector(conf=args.conf, model_path=Path(args.model))

    def _draw_counts(frame, result):
        out = result.annotated
        counts: dict[str, int] = {}
        for r in result.detections:
            counts[r["label"]] = counts.get(r["label"], 0) + 1
        y = 30
        for name, n in sorted(counts.items()):
            cv2.putText(out, f"{name}: {n}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            y += 28
        return out

    run_video(
        FrameProcessor(detectors=[detector]),
        VideoRunConfig(
            video_path=video_path,
            show=args.show,
            max_frames=args.max_frames,
            window_title="Person Detection",
            on_frame=_draw_counts,
        ),
    )
    return 0
