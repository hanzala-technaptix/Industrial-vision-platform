"""Unified Event Schema for Backend and CV-Pipeline"""
from pydantic import BaseModel
from typing import Optional, List


class EventSchema(BaseModel):
    """Event schema for both CV-Pipeline and Backend API"""
    event_id: Optional[str] = None
    event_type: str
    confidence: float
    camera_id: str
    bbox: List[float]
    timestamp: Optional[float] = None


class Event:
    """Event class for CV-Pipeline service"""
    def __init__(self, event_type: str, confidence: float, camera_id: str, 
                 bbox: List[float], timestamp: float, event_id: Optional[str] = None):
        self.event_id = event_id
        self.event_type = event_type
        self.confidence = confidence
        self.camera_id = camera_id
        self.bbox = bbox
        self.timestamp = timestamp

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "confidence": self.confidence,
            "camera_id": self.camera_id,
            "bbox": self.bbox,
            "timestamp": self.timestamp
        }
