import cv2
from config import COLOR_PAD, COLOR_LOCK

def draw_object(frame, obj):
    x, y, w, h = [int(v) for v in obj.bbox]
    color = obj.color()
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

    label = f"ID {obj.id}"
    if obj.class_name:
        label += f" {obj.class_name} {obj.confidence:.2f}"
    cv2.putText(frame, label, (x, max(0, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # траєкторія
    pts = list(obj.trajectory)
    for i in range(1, len(pts)):
        p1 = (pts[i - 1][1], pts[i - 1][2])
        p2 = (pts[i][1], pts[i][2])
        cv2.line(frame, p1, p2, (0, 0, 255), 2)


def draw_pad_bbox(frame, bbox, dx, dy, z_percent):
    x, y, w, h = [int(v) for v in bbox]
    cv2.rectangle(frame, (x, y), (x + w, y + h), COLOR_PAD, 2)
    label = f"PAD dx={dx:.0f}px dy={dy:.0f}px Z={z_percent:.1f}%"
    cv2.putText(frame, label, (x, max(0, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_PAD, 2)

def draw_locked_target(frame, bbox, class_name, confidence):
    x, y, w, h = [int(v) for v in bbox]
    cv2.rectangle(frame, (x, y), (x + w, y + h), COLOR_LOCK, 3)
    label = f"LOCK {class_name} {confidence:.2f}".strip()
    cv2.putText(frame, label, (x, max(0, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_LOCK, 2)

def draw_banner(frame, lines, color=(255, 255, 255), origin=(10, 10)):
    if not lines:
        return 0

    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.55
    thickness = 2
    line_h = 24
    pad = 8

    max_text_w = max(cv2.getTextSize(line, font, scale, thickness)[0][0] for line in lines)
    box_w = max_text_w + pad * 2
    box_h = line_h * len(lines) + pad * 2

    x, y = origin
    x2, y2 = min(x + box_w, frame.shape[1]), min(y + box_h, frame.shape[0])

    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x2, y2), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    for i, line in enumerate(lines):
        ty = y + pad + line_h * (i + 1) - 6
        cv2.putText(frame, line, (x + pad, ty), font, scale, color, thickness, cv2.LINE_AA)

    return box_h

def draw_banners(frame, banners, origin=(10, 10), gap=6):
    x, y = origin
    for lines, color in banners:
        if not lines:
            continue
        banner_h = draw_banner(frame, lines, color=color, origin=(x, y))
        y += banner_h + gap