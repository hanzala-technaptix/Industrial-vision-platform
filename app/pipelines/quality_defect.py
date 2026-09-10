"""Use case 05 — still-image quality inspection (MVTec AD).

Walks test stills and overlays GOOD / DEFECT. Same detector as the dashboard.
"""
from __future__ import annotations

import argparse

import cv2

from app.analytics.quality import QualityDetector, list_quality_stills
from app.pipeline.frame_processor import FrameProcessor
from app.rendering.overlays import draw_quality_status


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Quality defect (MVTec still images)")
    ap.add_argument("--category", default=None)
    ap.add_argument("--max-images", type=int, default=0)
    ap.add_argument("--show", action="store_true", default=True)
    args = ap.parse_args(argv)

    images = list_quality_stills(args.category)
    if not images:
        print("ERROR: no quality stills. Put images in test-images/quality/ or data/quality/mvtec/")
        return 2
    if args.max_images:
        images = images[: args.max_images]

    detector = QualityDetector()
    processor = FrameProcessor(detectors=[detector], post_draw=draw_quality_status)
    try:
        processor.setup()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    print(f"[quality] {len(images)} stills  (q/ESC quit, any key next)")

    for i, path in enumerate(images, start=1):
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        result = processor.process(frame, i)
        pred = (result.detections[0].get("label") if result.detections else "?")
        truth = path.parent.name
        print(f"  {i:03d}  truth={truth:16s}  pred={pred}  {path.name}")
        if args.show:
            cv2.imshow("Quality defect", result.annotated)
            key = cv2.waitKey(0) & 0xFF
            if key in (27, ord("q")):
                break

    processor.cleanup()
    cv2.destroyAllWindows()
    return 0
