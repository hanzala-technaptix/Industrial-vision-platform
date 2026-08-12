"""Reference only — extracted from Hospitality Safety Vision (R3) imageDetection.py.

Keep item from Factory AI POC audit: classify_completion() + calculate_iou().
Not wired into the runtime pipeline; use when implementing app/detectors/ppe_detector.py.
"""


def classify_completion(predictions, labels):
    person_bbox = None
    required_items = {"apron", "hairnet", "footwear", "person"}
    detected_items = set()
    iou_threshold = 0.6  # Adjust as needed
    iou_values = []

    # Store detected items before person detection
    stored_items = {}

    # Iterate through predictions to classify labels and extract bounding boxes
    for bbox, class_label in zip(predictions, labels):
        # Check if the label is 'person'
        if class_label == "person":
            person_bbox = bbox
            detected_items.add(class_label)

            # Calculate IOU with previously detected items
            for item_label, stored_bbox in stored_items.items():
                iou = calculate_iou(person_bbox, stored_bbox)
                iou_values.append(f"IOU between person and {item_label}: {iou:.2f}")
                if iou >= iou_threshold:
                    detected_items.add(item_label)

        # Check if the label is in the required items
        if class_label in required_items:
            # If person_bbox is not detected yet, store the item for later calculation
            if person_bbox is None:
                stored_items[class_label] = bbox
            else:
                # Calculate IOU with person bbox
                iou = calculate_iou(person_bbox, bbox)
                iou_values.append(f"IOU between person and {class_label}: {iou:.2f}")
                if class_label == "hairnet":
                    iou += 0.25
                if iou >= iou_threshold:
                    detected_items.add(class_label)

    if "person" not in detected_items:
        return "background"
    elif detected_items == required_items:
        return "complete"
    elif detected_items == {"hairnet", "apron"}:
        return "partial complete"
    else:
        return "not complete"


def calculate_iou(box1, box2):
    # Convert bounding box coordinates to (x1, y1, x2, y2) format
    box1_coords = [box1[0], box1[1], box1[2], box1[3]]
    box2_coords = [box2[0], box2[1], box2[2], box2[3]]

    # Calculate intersection coordinates
    x_left = max(box1_coords[0], box2_coords[0])
    y_top = max(box1_coords[1], box2_coords[1])
    x_right = min(box1_coords[2], box2_coords[2])
    y_bottom = min(box1_coords[3], box2_coords[3])

    # Calculate intersection area
    intersection_area = max(0, x_right - x_left) * max(0, y_bottom - y_top)

    # Calculate areas of both bounding boxes
    box1_area = (box1_coords[2] - box1_coords[0]) * (box1_coords[3] - box1_coords[1])
    box2_area = (box2_coords[2] - box2_coords[0]) * (box2_coords[3] - box2_coords[1])

    # Calculate union area
    union_area = box1_area + box2_area - intersection_area

    # Calculate IOU
    iou = intersection_area / union_area if union_area > 0 else 0
    return iou
