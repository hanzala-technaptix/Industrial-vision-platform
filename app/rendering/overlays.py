"""UI overlays — alert panels, zone, machine status."""
from __future__ import annotations

import cv2
import numpy as np


def render_alert_panel(messages: list[str], *, width: int = 520):
    if not messages:
        return None

    line_h = 34
    header_h = 44
    pad = 12
    panel_h = header_h + pad + line_h * min(len(messages), 8) + pad
    panel = np.zeros((panel_h, width, 3), dtype=np.uint8)
    panel[:] = (20, 20, 30)

    cv2.rectangle(panel, (0, 0), (width - 1, header_h), (0, 0, 160), -1)
    cv2.putText(
        panel, "PPE ALERTS", (pad, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA,
    )

    for i, msg in enumerate(messages[:8]):
        y = header_h + pad + (i + 1) * line_h - 8
        cv2.putText(
            panel, msg, (pad, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.62, (220, 220, 255), 2, cv2.LINE_AA,
        )

    cv2.rectangle(panel, (0, 0), (width - 1, panel_h - 1), (0, 0, 255), 3)
    return panel


def draw_zone_overlay(frame, polygon, present: bool):
    overlay = frame.copy()
    color = (0, 255, 0) if present else (0, 0, 255)
    cv2.fillPoly(overlay, [polygon], color)
    cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
    cv2.polylines(frame, [polygon], True, color, 2)
    text = "PRESENT" if present else "ABSENT"
    cv2.putText(frame, f"Zone: {text}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
    return frame


def draw_person_count(frame, detections):
    n = sum(1 for d in detections if str(d.get("label") or "").lower() == "person")
    cv2.rectangle(frame, (10, 10), (240, 58), (0, 0, 0), -1)
    cv2.putText(frame, f"People: {n}", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    return frame


def draw_worker_status(frame, detections):
    meta = {}
    for row in detections:
        if (row.get("metadata") or {}).get("role") == "worker":
            meta = row.get("metadata") or {}
            break
    state = meta.get("state", "absent")
    if state == "absent":
        color, label = (0, 0, 255), "ABSENT"
    elif state == "active":
        color, label = (0, 255, 0), "ACTIVE"
    else:
        color, label = (0, 255, 255), "IDLE"
    cv2.rectangle(frame, (10, 10), (540, 110), (0, 0, 0), -1)
    cv2.rectangle(frame, (10, 10), (540, 110), color, 2)
    cv2.putText(frame, f"Worker: {label}", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
    if state != "absent":
        cv2.putText(
            frame,
            f"Idle: {meta.get('idle_seconds', 0):.1f}s / {int(meta.get('idle_threshold', 8))}s"
            f"  motion={meta.get('motion', 0):.3f}",
            (20, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2,
        )
    return frame


def draw_count_line(frame, detections):
    h, w = frame.shape[:2]
    counter = next((r for r in detections if r.get("label") == "LineCount"), None)
    if counter is None:
        return frame
    meta = counter.get("metadata") or {}
    lx = int(meta.get("line_x", w // 2))
    cv2.line(frame, (lx, 0), (lx, h), (255, 255, 0), 2)
    cv2.putText(
        frame, f"Count: {meta.get('count', 0)}", (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 2,
    )
    return frame


def draw_downtime_hud(frame, detections, running_s: float = 0.0, idle_s: float = 0.0):
    meta = {}
    for row in detections:
        if (row.get("metadata") or {}).get("role") == "machine":
            meta = row.get("metadata") or {}
            break
    state = meta.get("state", "idle")
    total = running_s + idle_s
    uptime = (running_s / total * 100) if total else 0.0
    color = (0, 255, 0) if state != "idle" else (0, 0, 255)
    cv2.rectangle(frame, (10, 10), (520, 120), (0, 0, 0), -1)
    cv2.rectangle(frame, (10, 10), (520, 120), color, 2)
    cv2.putText(
        frame, f"Line: {'RUNNING' if state != 'idle' else 'IDLE'}",
        (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2,
    )
    cv2.putText(
        frame,
        f"Uptime {uptime:.0f}%   run {running_s:.0f}s   idle {idle_s:.0f}s",
        (20, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
    )
    return frame


def draw_machine_status(frame, state: str, idle_seconds: float, threshold: float, motion_val: float):
    label = "RUNNING" if state == "active" else "IDLE"
    color = (0, 255, 0) if state == "active" else (0, 0, 255)
    cv2.rectangle(frame, (10, 10), (440, 110), (0, 0, 0), -1)
    cv2.rectangle(frame, (10, 10), (440, 110), color, 2)
    cv2.putText(frame, f"Status: {label}", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
    cv2.putText(
        frame, f"Idle: {idle_seconds:.1f}s",
        (20, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2,
    )
    cv2.putText(
        frame, f"Motion: {motion_val:.3f}", (20, 102),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1,
    )
    if state == "idle":
        flash = frame.copy()
        cv2.rectangle(flash, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 255), 8)
        cv2.addWeighted(flash, 0.4, frame, 0.6, 0, frame)
    return frame


def draw_quality_status(frame, detections):
    row = detections[0] if detections else {}
    label = str(row.get("label") or "unknown").upper()
    ok = (row.get("metadata") or {}).get("ok")
    color = (0, 200, 0) if ok else (0, 0, 255)
    cv2.rectangle(frame, (10, 10), (420, 70), (0, 0, 0), -1)
    cv2.rectangle(frame, (10, 10), (420, 70), color, 2)
    cv2.putText(
        frame, f"{label}  {float(row.get('confidence') or 0):.2f}",
        (20, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2,
    )
    return frame
