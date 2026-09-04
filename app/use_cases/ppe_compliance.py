"""Use case 01 — PPE compliance (helmet / mask / vest / gloves)."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.pipeline.frame_processor import FrameProcessor
from demos._paths import DEFAULT_VIDEOS, LOG_DIR
from demos.lib.video_runner import VideoRunConfig, run_video


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PPE compliance use case")
    ap.add_argument("video", nargs="?", help="Input video")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--conf", type=float, default=None)
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args(argv)

    video_path = Path(args.video or DEFAULT_VIDEOS["ppe"]).resolve()
    if not video_path.exists():
        print(f"ERROR: video not found: {video_path}")
        return 2

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    db_path = LOG_DIR / "ppe_demo.db"
    if db_path.exists():
        db_path.unlink()

    if args.conf is not None:
        os.environ["PPE_CONF_THRESHOLD"] = str(args.conf)
    os.environ["DB_PATH"] = str(db_path)

    from app.alerts.manager import AlertManager
    from app.alerts.ppe import PPEAlertTracker
    from app.core.config import (
        PPE_CONF_THRESHOLD,
        PPE_REQUIRED_ITEMS,
        PPE_VIOLATION_COOLDOWN,
        PPE_VIOLATION_MIN_FRAMES,
    )
    from app.detectors.ppe import PPEDetector
    from app.events.engine import EventEngine
    from app.events.repository import event_stats, list_events
    from app.rendering.detections import ppe_display_name

    processor = FrameProcessor(
        detectors=[PPEDetector(camera_id="ppe_demo")],
        event_engine=EventEngine(),
        alert_manager=AlertManager([PPEAlertTracker(PPE_REQUIRED_ITEMS)]),
        camera_id="ppe_demo",
    )
    out_path = Path(args.out) if args.out else (None if args.show else LOG_DIR / "ppe_demo_out.mp4")

    print(f"[ppe] {video_path.name}  conf={PPE_CONF_THRESHOLD}")
    print(f"[ppe] enforcing: {', '.join(PPE_REQUIRED_ITEMS)}")
    if out_path:
        print(f"[ppe] output: {out_path}")

    def _log_alerts(frame, result):
        for item in result.detections:
            meta = item.get("metadata") or {}
            if meta.get("alert_removed"):
                tid = item.get("track_id")
                names = ", ".join(ppe_display_name(p) for p in meta["alert_removed"])
                print(f"[ppe] ALERT Person #{tid}: {names} REMOVED")
        return result.annotated

    stats = run_video(
        processor,
        VideoRunConfig(
            video_path=video_path,
            camera_id="ppe_demo",
            stride=args.stride,
            max_frames=args.max_frames,
            show=args.show,
            out_path=out_path,
            window_title="PPE Compliance",
            alert_window="PPE Alerts",
            db_path=db_path,
            on_frame=_log_alerts,
        ),
    )

    ev_stats = event_stats()
    events = list_events(limit=500)

    print(f"\n=== PPE SUMMARY ===")
    print(f"processed {stats.processed} frames in {stats.elapsed_s:.1f}s")
    print(f"person tracks: {sorted(stats.person_tracks)}")
    print("detections by class:")
    for k, v in sorted(stats.class_counts.items(), key=lambda x: -x[1]):
        print(f"  {k:20s} {v}")
    print(f"events: {json.dumps(ev_stats, indent=2)}")
    for e in events[:10]:
        print(f"  {e['event_type']}  {e.get('event_subtype')}  track={e.get('track_id')}")

    if args.report:
        report_path = video_path.with_name(video_path.stem + "_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "input": str(video_path),
                "frames_processed": stats.processed,
                "class_counts": stats.class_counts,
                "stats": ev_stats,
                "events": events,
                "params": {
                    "conf": PPE_CONF_THRESHOLD,
                    "min_frames": PPE_VIOLATION_MIN_FRAMES,
                    "cooldown": PPE_VIOLATION_COOLDOWN,
                    "stride": args.stride,
                },
            }, f, indent=2)
        print(f"[ppe] report: {report_path}")
    return 0
