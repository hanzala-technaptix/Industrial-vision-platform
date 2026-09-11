"""Use case 03 — Restricted zone presence."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from app.core.bbox import is_valid_bbox
from app.analytics.zones import ZoneDetector, default_zone
from app.pipeline.frame_processor import FrameProcessor
from app.rendering.overlays import draw_zone_overlay
from app.core.videos import DEFAULT_VIDEOS
from demos.lib.video_runner import VideoRunConfig, run_video


def _parse_zone(zone_str: str) -> np.ndarray:
    pts = [[int(x), int(y)] for x, y in (p.split(",") for p in zone_str.strip().split())]
    return np.array(pts, dtype=np.int32)


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Restricted zone presence")
    ap.add_argument("--source", default=str(DEFAULT_VIDEOS["zone"]))
    ap.add_argument("--zone", type=_parse_zone, default=None,
                    help="Polygon like 'x1,y1 x2,y2 ...'")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--show", action="store_true", default=True)
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args(argv)

    video_path = Path(args.source).resolve()
    if not video_path.exists():
        print(f"Error: Cannot open {args.source}")
        return 1

    cap = cv2.VideoCapture(str(video_path))
    _, first = cap.read()
    cap.release()

    detector = ZoneDetector(zone_polygon=args.zone, conf=args.conf)
    if args.zone is None and first is not None:
        detector.zone = default_zone(first)

    def _zone_overlay(frame, result):
        present = False
        out = result.annotated
        polygon = np.array(detector.zone, dtype=np.int32)
        for r in result.detections:
            if r.get("label") == "Zone":
                present = bool((r.get("metadata") or {}).get("present"))
            bbox = r.get("bbox")
            if is_valid_bbox(bbox) and str(r.get("label") or "").lower() == "person":
                x1, y1, x2, y2 = map(int, bbox)
                cv2.circle(out, (int((x1 + x2) / 2), y2), 6, (0, 255, 255), -1)
        return draw_zone_overlay(out, polygon, present)

    run_video(
        FrameProcessor(detectors=[detector]),
        VideoRunConfig(
            video_path=video_path,
            show=args.show,
            max_frames=args.max_frames,
            window_title="Restricted Zone",
            on_frame=_zone_overlay,
        ),
    )
    return 0
