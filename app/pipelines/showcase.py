"""Live showcase catalog — one entry per CEO demo.

The API switches these at runtime. CLI scripts in demos/ still call the
matching pipelines/*.py modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from app.core.videos import expected_path, video_sources
from app.detection.base import BaseDetector
from app.analytics.machine_idle import MachineIdleDetector
from app.analytics.quality import QualityDetector, quality_ready, quality_source_dir
from app.detection.person import PersonDetector
from app.detection.ppe import PPEDetector
from app.analytics.counting import ProductCountingDetector
from app.analytics.worker_idle import WorkerIdleDetector
from app.analytics.zones import ZoneDetector, default_zone
from app.rendering.overlays import (
    draw_count_line,
    draw_person_count,
    draw_quality_status,
    draw_worker_status,
    draw_zone_overlay,
)


@dataclass(frozen=True)
class UseCaseSpec:
    id: str
    number: str
    title: str
    summary: str
    video_key: str
    engine: str = "model"
    alerts: bool = False


def _ppe_draw(frame, detections):
    return frame


def _person_draw(frame, detections):
    return draw_person_count(frame, detections, hud=False)


def _zone_draw(frame, detections):
    present = False
    polygon = None
    for row in detections:
        meta = row.get("metadata") or {}
        if row.get("label") == "Zone":
            present = bool(meta.get("present"))
            if meta.get("polygon"):
                polygon = np.array(meta["polygon"], dtype=np.int32)
    if polygon is None:
        polygon = default_zone(frame)
    return draw_zone_overlay(frame, polygon, present, hud=False)


def _worker_draw(frame, detections):
    return draw_worker_status(frame, detections, hud=False)


def _count_draw(frame, detections):
    return draw_count_line(frame, detections, hud=False)


def _machine_roi(frame, detections):
    for row in detections:
        meta = row.get("metadata") or {}
        if meta.get("role") == "machine" and meta.get("roi_polygon"):
            import cv2

            poly = np.array(meta["roi_polygon"], dtype=np.int32)
            cv2.polylines(frame, [poly], True, (0, 255, 255), 2)
            break
    return frame


def _machine_draw(frame, detections):
    return _machine_roi(frame, detections)


def _downtime_draw(frame, detections):
    return _machine_roi(frame, detections)


def _quality_draw(frame, detections):
    return draw_quality_status(frame, detections, hud=False)


SPECS: Dict[str, UseCaseSpec] = {
    "ppe": UseCaseSpec("ppe", "01", "PPE compliance", "Helmet, mask, vest, gloves", "ppe", engine="model", alerts=True),
    "person": UseCaseSpec("person", "02", "Person detection", "People on the floor", "person", engine="model"),
    "zone": UseCaseSpec("zone", "03", "Restricted zone", "Person model + zone polygon", "zone", engine="hybrid"),
    "product_counting": UseCaseSpec("product_counting", "04", "Product counting", "Motion blobs crossing a line", "product_counting", engine="motion"),
    "quality": UseCaseSpec("quality", "05", "Quality defect", "GOOD / DEFECT on inspection stills", "quality", engine="model"),
    "machine_idle": UseCaseSpec("machine_idle", "06", "Machine idle", "Running vs idle from motion", "machine_idle", engine="motion"),
    "worker_idle": UseCaseSpec("worker_idle", "07", "Worker idle", "Person model + motion in the box", "worker_idle", engine="hybrid"),
    "downtime": UseCaseSpec("downtime", "08", "Downtime analytics", "Live running vs idle share", "downtime", engine="motion"),
}

_DRAW: Dict[str, Callable] = {
    "ppe": _ppe_draw,
    "person": _person_draw,
    "zone": _zone_draw,
    "product_counting": _count_draw,
    "quality": _quality_draw,
    "machine_idle": _machine_draw,
    "worker_idle": _worker_draw,
    "downtime": _downtime_draw,
}


def list_specs() -> List[UseCaseSpec]:
    return list(SPECS.values())


def get_spec(use_case_id: str) -> UseCaseSpec:
    if use_case_id not in SPECS:
        known = ", ".join(SPECS)
        raise KeyError(f"Unknown use case '{use_case_id}'. Known: {known}")
    return SPECS[use_case_id]


def video_for(spec: UseCaseSpec):
    if spec.id == "quality":
        return quality_source_dir() if quality_ready() else None
    sources = video_sources(spec.video_key)
    if not sources:
        return None
    if len(sources) == 1:
        return sources[0]
    return sources


def describe(spec: UseCaseSpec) -> Dict[str, Any]:
    video = video_for(spec)
    if spec.id == "quality":
        from app.core.config import QUALITY_MODEL_PATH

        expected = (
            str(QUALITY_MODEL_PATH)
            if not QUALITY_MODEL_PATH.exists()
            else str(quality_source_dir() or "data/quality/mvtec")
        )
    else:
        expected = str(expected_path(spec.video_key))
    return {
        "id": spec.id,
        "number": spec.number,
        "title": spec.title,
        "summary": spec.summary,
        "ready": video is not None,
        "engine": spec.engine,
        "video": (
            " | ".join(str(p) for p in video)
            if isinstance(video, list)
            else (str(video) if video else None)
        ),
        "expected_video": expected,
        "alerts": spec.alerts,
    }


def build_detectors(spec: UseCaseSpec, camera_id: str) -> List[BaseDetector]:
    if spec.id == "ppe":
        return [PPEDetector(camera_id=camera_id)]
    if spec.id == "person":
        return [PersonDetector(camera_id=camera_id)]
    if spec.id == "zone":
        return [ZoneDetector(camera_id=camera_id)]
    if spec.id == "worker_idle":
        return [WorkerIdleDetector(camera_id=camera_id)]
    if spec.id == "product_counting":
        return [ProductCountingDetector(camera_id=camera_id)]
    if spec.id == "quality":
        return [QualityDetector(camera_id=camera_id)]
    if spec.id in ("machine_idle", "downtime"):
        return [MachineIdleDetector(camera_id=camera_id)]
    raise KeyError(spec.id)


def post_draw_for(spec: UseCaseSpec) -> Callable:
    return _DRAW[spec.id]
