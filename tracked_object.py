class TrackedObject:
    __slots__ = ("id", "bbox", "class_name", "confidence")

    def __init__(self, id, bbox, class_name, confidence):
        self.id = id                    # tracker_id з ByteTrack
        self.bbox = bbox                # (x, y, w, h) - лівий верхній кут + ширина/висота
        self.class_name = class_name
        self.confidence = confidence

def build_tracked_objects(detections, class_names):
    objects = []
    if len(detections) == 0 or detections.tracker_id is None:
        return objects

    for bbox_xyxy, tracker_id, class_id, confidence in zip(
        detections.xyxy, detections.tracker_id, detections.class_id, detections.confidence
    ):
        if tracker_id is None:
            continue
        x1, y1, x2, y2 = bbox_xyxy
        bbox_xywh = (float(x1), float(y1), float(x2 - x1), float(y2 - y1))
        objects.append(TrackedObject(
            id=int(tracker_id),
            bbox=bbox_xywh,
            class_name=class_names[int(class_id)],
            confidence=float(confidence),
        ))
    return objects