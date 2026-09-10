"""Use case 04 — Product counting on a conveyor."""
from __future__ import annotations

import argparse

import cv2

from app.analytics.counting import ProductCountingDetector
from app.pipeline.frame_processor import FrameProcessor
from app.core.videos import require_video
from demos.lib.video_runner import VideoRunConfig, run_video


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Product counting (line cross)")
    ap.add_argument("--source", default=None)
    ap.add_argument("--motion-threshold", type=int, default=25)
    ap.add_argument("--min-area", type=int, default=400)
    ap.add_argument("--line-x", type=int, default=None,
                    help="Vertical line position; default = frame center")
    ap.add_argument("--show", action="store_true", default=True)
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args(argv)

    video_path = require_video("product_counting", args.source)

    detector = ProductCountingDetector(
        motion_threshold=args.motion_threshold,
        min_area=args.min_area,
        line_x=args.line_x,
    )

    def _overlay(frame, result):
        out = result.annotated
        h, w = out.shape[:2]
        counter = next(
            (r for r in result.detections if r.get("label") == "LineCount"),
            None,
        )
        if counter is not None:
            meta = counter.get("metadata") or {}
            lx = int(meta.get("line_x", w // 2))
            cv2.line(out, (lx, 0), (lx, h), (255, 255, 0), 2)
            cv2.putText(out, f"Count: {meta.get('count', 0)}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 2)
        return out

    stats = run_video(
        FrameProcessor(detectors=[detector]),
        VideoRunConfig(
            video_path=video_path,
            show=args.show,
            max_frames=args.max_frames,
            window_title="Product Counting",
            on_frame=_overlay,
        ),
    )
    print(f"[counting] final count: {detector.get_state().get('count')}")
    print(f"[counting] processed {stats.processed} frames in {stats.elapsed_s:.1f}s")
    return 0
