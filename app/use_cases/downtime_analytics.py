"""Use case 08 — Offline downtime analytics timeline from a machine video.

Not a live camera loop — reads a video file end to end, uses MachineIdleDetector
to classify each frame, then reports running/idle segments.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import cv2

from app.detectors.machine_idle import MachineIdleDetector
from demos._paths import require_machine_video


@dataclass
class Segment:
    state: str
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Downtime analytics (offline)")
    ap.add_argument("--source", default=None, help="Factory/line MP4 path")
    ap.add_argument("--fps-assume", type=float, default=0.0, help="0 = read from video")
    ap.add_argument("--motion-threshold", type=float, default=0.5)
    ap.add_argument("--idle-seconds", type=float, default=1.0)
    args = ap.parse_args(argv)

    video_path = require_machine_video(args.source)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error: Cannot open {video_path}")
        return 1

    fps = args.fps_assume or cap.get(cv2.CAP_PROP_FPS) or 25.0
    detector = MachineIdleDetector(
        idle_seconds=args.idle_seconds,
        motion_threshold=args.motion_threshold,
    )
    detector.setup()

    segments: list[Segment] = []
    current_state = "running"
    segment_start = 0.0
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1
        rows = detector.process(frame, frame_idx)
        meta = (rows[0].get("metadata") if rows else {}) or {}
        state = meta.get("state", "active")
        # Detector uses "active"/"idle"; normalize to running/idle for reporting
        new_state = "idle" if state == "idle" else "running"
        t = frame_idx / fps
        if new_state != current_state:
            segments.append(Segment(current_state, segment_start, t))
            current_state = new_state
            segment_start = t

    total_s = frame_idx / fps if fps else 0.0
    segments.append(Segment(current_state, segment_start, total_s))
    cap.release()
    detector.cleanup()

    running_s = sum(s.duration_s for s in segments if s.state == "running")
    idle_s = sum(s.duration_s for s in segments if s.state == "idle")
    uptime_pct = (running_s / total_s * 100) if total_s else 0

    print("\n=== DOWNTIME ANALYTICS ===")
    print(f"source:     {video_path}")
    print(f"duration:   {total_s:.1f}s")
    print(f"running:    {running_s:.1f}s")
    print(f"idle:       {idle_s:.1f}s")
    print(f"uptime:     {uptime_pct:.1f}%")
    print("\nTimeline:")
    for s in segments:
        print(f"  {s.start_s:6.1f}s - {s.end_s:6.1f}s  {s.state.upper():7s}  ({s.duration_s:.1f}s)")
    return 0
