"""BaseDetector ABC — every detector implements this."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypedDict


class DetectionResult(TypedDict, total=False):
    detector: str
    label: str
    confidence: float
    bbox: List[float]  # xyxy
    track_id: Optional[int]
    metadata: Dict[str, Any]


class BaseDetector(ABC):
    name: str = "base"
    frame_stride: int = 1  # process every Nth frame; 1 = every frame

    def __init__(self, camera_id: str = "cam"):
        self.camera_id = camera_id
        self.enabled = True

    def setup(self) -> None:
        """Load weights, warm up. Called once at pipeline start."""
        pass

    @abstractmethod
    def process(self, frame, frame_count: int) -> List[DetectionResult]:
        raise NotImplementedError

    def get_state(self) -> Dict[str, Any]:
        return {"detector": self.name, "enabled": self.enabled}

    def cleanup(self) -> None:
        pass
