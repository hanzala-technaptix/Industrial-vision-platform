import time
import math

from app.utils.bbox import is_valid_bbox


class TrackedObject:
    """Represents a tracked object across frames"""
    
    def __init__(self, id, bbox):
        self.id = id
        self.bbox = bbox
        self.last_seen = time.time()

    def update(self, bbox):
        """Update object location"""
        self.bbox = bbox
        self.last_seen = time.time()

    def is_stale(self, timeout=2.0):
        """Check if object hasn't been seen in timeout seconds"""
        return (time.time() - self.last_seen) > timeout

    def distance_to(self, bbox):
        """Calculate distance between object and detection bbox"""
        x1_old, y1_old, x2_old, y2_old = self.bbox
        x1_new, y1_new, x2_new, y2_new = bbox
        
        # Center coordinates
        cx_old = (x1_old + x2_old) / 2
        cy_old = (y1_old + y2_old) / 2
        cx_new = (x1_new + x2_new) / 2
        cy_new = (y1_new + y2_new) / 2
        
        # Euclidean distance
        return math.sqrt((cx_new - cx_old) ** 2 + (cy_new - cy_old) ** 2)

    
class ObjectTracker:
    """
    Maintains object identity across frames using bbox similarity.
    Assigns and updates track_ids for detections.
    """
    
    def __init__(self, distance_threshold=100):
        self.objects = {}  # id -> TrackedObject
        self.next_id = 0
        self.distance_threshold = distance_threshold

    def update(self, detections):
        """
        Update tracker with new detections.
        Assigns/updates track_ids for each detection.
        
        Args:
            detections: list of dicts with keys: label, confidence, bbox, track_id
        
        Returns:
            dict of tracked objects (id -> TrackedObject)
        """
        current_ids = set()
        
        for det in detections:
            if not isinstance(det, dict):
                continue
            bbox = det.get("bbox")
            if not is_valid_bbox(bbox):
                continue

            best_match_id = None
            best_distance = self.distance_threshold
            
            # Find closest existing object
            for obj_id, obj in self.objects.items():
                distance = obj.distance_to(bbox)
                if distance < best_distance:
                    best_distance = distance
                    best_match_id = obj_id
            
            # Assign or create track_id
            if best_match_id is not None:
                # Update existing object
                self.objects[best_match_id].update(bbox)
                det['track_id'] = best_match_id
                current_ids.add(best_match_id)
            else:
                # Create new object
                new_id = self.next_id
                self.objects[new_id] = TrackedObject(new_id, bbox)
                det['track_id'] = new_id
                current_ids.add(new_id)
                self.next_id += 1
        
        # Remove stale objects (not seen for timeout)
        stale_ids = [oid for oid, obj in self.objects.items() 
                     if oid not in current_ids and obj.is_stale(timeout=3.0)]
        
        for oid in stale_ids:
            del self.objects[oid]

        return self.objects

