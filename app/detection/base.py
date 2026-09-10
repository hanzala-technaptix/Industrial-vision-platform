"""Base detector interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, TypedDict


class DetectionResult(TypedDict, total=False):
    detector: str
    label: str
    confidence: float
    bbox: List[float]
    track_id: int | None
    metadata: Dict[str, Any]


class BaseDetector(ABC):
    name: str = "base"
    frame_stride: int = 1

    def __init__(self, camera_id: str = "cam"):
        self.camera_id = camera_id
        self.enabled = True

    def setup(self) -> None:
        pass

    @abstractmethod
    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        raise NotImplementedError

    def get_state(self) -> Dict[str, Any]:
        return {"detector": self.name, "enabled": self.enabled}

    def cleanup(self) -> None:
        pass
