"""Run the Phase 1 PPE pipeline against a video file.

Usage (from repo root, with venv activated):
    python scripts/test_ppe_video.py <path/to/video.mp4> [--out out.mp4] [--conf 0.35] [--show]

Produces:
    * <video>.json    — every event that fired (violations + recoveries)
    * console summary — stats + timings
    * live preview window when --show is passed (press q or ESC to quit)

Engineering flow (Phase 1):
    1. Person detection
       ↓
    2. Person tracking
       ↓
    3. PPE detection
       ↓
    4. PPE → Person association
       ↓
    5. Per-person state
       ↓
    6. Temporal confirmation
       ↓
    7. EventEngine emits PPE violation/recovery events
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Make `app` importable when running the script directly
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Test Phase 1 PPE pipeline on a video file")
    ap.add_argument("video", help="Path to input video")
    ap.add_argument("--conf", type=float, default=None, help="Override PPE_CONF_THRESHOLD (default from .env / config)")
    ap.add_argument("--min-frames", type=int, default=None, help="Override PPE_VIOLATION_MIN_FRAMES")
    ap.add_argument("--cooldown", type=float, default=None, help="Override PPE_VIOLATION_COOLDOWN (seconds)")
    ap.add_argument("--stride", type=int, default=1, help="Process every Nth frame (1 = every frame)")
    ap.add_argument("--max-frames", type=int, default=0, help="Stop after N frames (0 = all)")
    ap.add_argument("--show", action="store_true", help="Preview window while processing (press q to quit)")
    ap.add_argument("--db", default=str(ROOT / "data" / "_scenario_test.db"), help="SQLite path (fresh each run)")
    args = ap.parse_args()

    video_path = Path(args.video).resolve()
    if not video_path.exists():
        print(f"ERROR: video not found: {video_path}")
        return 2
    json_path = video_path.with_name(video_path.stem + "_report.json")

    # Env overrides must be set BEFORE importing app.config
    if args.conf is not None:       os.environ["PPE_CONF_THRESHOLD"] = str(args.conf)
    if args.min_frames is not None: os.environ["PPE_VIOLATION_MIN_FRAMES"] = str(args.min_frames)
    if args.cooldown is not None:   os.environ["PPE_VIOLATION_COOLDOWN"] = str(args.cooldown)
    os.environ["DB_PATH"] = args.db

    # Fresh DB
    if Path(args.db).exists():
        Path(args.db).unlink()

    from app.config import PPE_CONF_THRESHOLD, PPE_VIOLATION_COOLDOWN, PPE_VIOLATION_MIN_FRAMES
    from app.db.database import event_stats, init_db, list_events
    from app.detectors.ppe_detector import PPEDetector
    from app.events.engine import EventEngine
    from app.utils.draw import draw_detections

    init_db()
    det = PPEDetector(camera_id=video_path.stem)
    det.setup()
    engine = EventEngine()

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"ERROR: cannot open {video_path}")
        return 3

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 360)
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_in = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    print(f"[test] input:  {video_path}  ({w}x{h} @ {fps_in:.1f}fps, ~{total_in} frames)")
    print(f"[test] report: {json_path}")
    print(f"[test] conf={PPE_CONF_THRESHOLD}  min_frames={PPE_VIOLATION_MIN_FRAMES}  cooldown={PPE_VIOLATION_COOLDOWN}s  stride={args.stride}")

    frame_no = 0
    processed = 0
    class_counts: dict = {}
    person_tracks: set = set()
    t0 = time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_no += 1
        if args.stride > 1 and (frame_no % args.stride) != 0:
            continue
        processed += 1

        results = det.process(frame, frame_no)
        engine.process(results, camera_id=video_path.stem)

        for r in results:
            lbl = r.get("label", "?")
            class_counts[lbl] = class_counts.get(lbl, 0) + 1
            if lbl == "Person" and r.get("track_id") is not None:
                person_tracks.add(r["track_id"])

        if args.show:
            annotated = draw_detections(frame.copy(), results)
            if annotated is not None:
                cv2.imshow("PPE Test", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:  # q or ESC
                    break

        if processed % 60 == 0:
            fps = processed / max(1e-6, time.time() - t0)
            print(f"  … frame {frame_no}/{total_in}  processed={processed}  fps={fps:.1f}  tracks_seen={len(person_tracks)}")

        if args.max_frames and processed >= args.max_frames:
            break

    cap.release()
    if args.show: cv2.destroyAllWindows()

    dt = time.time() - t0
    stats = event_stats()
    events = list_events(limit=1000)

    print(f"\n=== SUMMARY ===")
    print(f"frames read:      {frame_no}")
    print(f"frames processed: {processed}   avg fps={processed / max(1e-6, dt):.1f}")
    print(f"detection totals by class:")
    for k, v in sorted(class_counts.items(), key=lambda x: -x[1]):
        print(f"  {k:20s} {v}")
    print(f"unique person tracks:  {len(person_tracks)}   ids={sorted(person_tracks)}")
    print(f"\n=== EVENT STATS ===")
    print(json.dumps(stats, indent=2))
    print(f"\n=== EVENTS ({len(events)}) ===")
    for e in events[:30]:
        ts = e.get("timestamp") or 0.0
        print(f"  #{e['id']:>4}  {e['event_type']:<15} [{e.get('event_subtype') or '-':<18}] "
              f"track={e.get('track_id')}  conf={(e.get('confidence') or 0):.2f}")
    if len(events) > 30:
        print(f"  … {len(events) - 30} more (see {json_path})")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "input": str(video_path),
            "frames_read": frame_no,
            "frames_processed": processed,
            "class_counts": class_counts,
            "unique_person_tracks": sorted(person_tracks),
            "stats": stats,
            "events": events,
            "params": {
                "conf": PPE_CONF_THRESHOLD,
                "min_frames": PPE_VIOLATION_MIN_FRAMES,
                "cooldown": PPE_VIOLATION_COOLDOWN,
                "stride": args.stride,
            },
        }, f, indent=2)

    print(f"\n[test] wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
