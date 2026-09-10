"""Alert tracker protocol."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class AlertTracker(ABC):
    @abstractmethod
    def update(self, detections: List[Dict[str, Any]]) -> List[str]:
        raise NotImplementedError
