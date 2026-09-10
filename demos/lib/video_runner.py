"""Generic video-file runner used by every use case demo.

No business/detection logic here — it just pushes frames through a
`FrameProcessor`, handles I/O (show/write), and returns run stats.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import cv2

from app.pipeline.frame_processor import FrameProcessor
from demos.lib.cli import destroy_windows, gui_available, show_alert_window, show_frame, wait_key


@dataclass
class VideoRunConfig:
    video_path: Path
    camera_id: str = "demo"
    stride: int = 2
    frame_delay_ms: int = 1
    max_frames: int = 0
    show: bool = False
    out_path: Optional[Path] = None
    report_path: Optional[Path] = None
    window_title: str = "Demo"
    alert_window: Optional[str] = None
    db_path: Optional[Path] = None
    on_frame: Optional[Callable] = None


@dataclass
class VideoRunStats:
    processed: int = 0
    class_counts: dict = field(default_factory=dict)
    person_tracks: set = field(default_factory=set)
    elapsed_s: float = 0.0


def run_video(processor: FrameProcessor, cfg: VideoRunConfig) -> VideoRunStats:
    if cfg.db_path is not None:
        from app.events.repository import init_db

        init_db()

    cap = cv2.VideoCapture(str(cfg.video_path))
    if not cap.isOpened():
        raise SystemExit(f"ERROR: cannot open {cfg.video_path}")

    fps_in = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 360)

    writer = None
    out_path = cfg.out_path
    if out_path is None and not cfg.show:
        out_path = cfg.video_path.parent / f"{cfg.video_path.stem}_out.mp4"
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps_in, (w, h)
        )

    if cfg.show and not gui_available():
        print("[demo] --show unavailable; writing video instead.")
        if writer is None and out_path is not None:
            writer = cv2.VideoWriter(
                str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps_in, (w, h)
            )

    processor.setup()
    stats = VideoRunStats()
    t0 = time.time()
    frame_no = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_no += 1
        if cfg.stride > 1 and (frame_no % cfg.stride) != 0:
            continue
        stats.processed += 1

        result = processor.process(frame, frame_no)
        if cfg.on_frame is not None:
            updated = cfg.on_frame(frame, result)
            if updated is not None:
                result.annotated = updated

        for r in result.detections:
            lbl = r.get("label", "?")
            stats.class_counts[lbl] = stats.class_counts.get(lbl, 0) + 1
            if lbl == "Person" and r.get("track_id") is not None:
                stats.person_tracks.add(r["track_id"])

        if result.annotated is not None:
            if writer is not None:
                writer.write(result.annotated)
            if show_frame(cfg.window_title, result.annotated, enabled=cfg.show):
                if cfg.alert_window:
                    show_alert_window(cfg.alert_window, result.alerts, enabled=cfg.show)
                if wait_key(cfg.frame_delay_ms) in (ord("q"), 27):
                    break

        if cfg.max_frames and stats.processed >= cfg.max_frames:
            break

    cap.release()
    if writer is not None:
        writer.release()
    processor.cleanup()
    destroy_windows(enabled=cfg.show)
    stats.elapsed_s = time.time() - t0
    return stats
