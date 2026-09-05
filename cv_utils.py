def to_int_bbox(bbox):
    # трекерам OpenCV (>=5.0) потрібні цілі (x, y, w, h)
    x, y, w, h = bbox
    return (int(x), int(y), int(w), int(h))

def bbox_iou(bbox_a, bbox_b):
    # IoU двох рамок (x, y, w, h): 0 - не перетинаються, 1 - повністю збігаються
    ax, ay, aw, ah = bbox_a
    bx, by, bw, bh = bbox_b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh

    inter_x1, inter_y1 = max(ax, bx), max(ay, by)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter_w, inter_h = max(0.0, inter_x2 - inter_x1), max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    union = aw * ah + bw * bh - inter_area
    return inter_area / union if union > 0 else 0.0

def compute_offset_and_scale(frame, bbox):
    # dx, dy - зсув центру bbox відносно центру кадру, в пікселях (від'ємне = лівіше/вище центру)
    # z_percent - яку частку кадру займає bbox, % (більше = ближче об'єкт)
    h_frame, w_frame = frame.shape[:2]
    x, y, w, h = bbox
    obj_cx, obj_cy = x + w / 2.0, y + h / 2.0
    dx = obj_cx - w_frame / 2.0
    dy = obj_cy - h_frame / 2.0

    frame_area = w_frame * h_frame
    z_percent = (w * h / frame_area * 100.0) if frame_area > 0 else 0.0

    return dx, dy, z_percent