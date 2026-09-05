# захват цілі вручну, клавіша F.
#
# якщо рамок декілька - береться та, у якої найбільший confidence. 
#
# поки ціль захоплена: малюється тільки її рамка (червона, LOCK), інші об'єкти без рамок.
#  return-to-station/пошук паду призупиняються, YOLO+трекер працюють як завжди.
#
# якщо ціль зникла з кадру - рамка залишається на останній відомій позиції
# FIRE_LOCK_LOST_GRACE_SEC секунд (config.py), і тільки якщо за цей час ціль не знайшлась -
# вона втрачаєтья (TARGET_LOST). Якщо знайшлась раніше - лічильник просто скидається.

import cv2
from config import COLOR_LOCK, FIRE_LOCK_LOST_GRACE_SEC
from cv_utils import compute_offset_and_scale
from drawing import draw_locked_target
from logger import log_event

def calculate_and_draw_offset(frame, bbox):
    # рахує і рисує вектор (dx, dy) від центру кадру до цілі, повертає (dx, dy, z_percent) -
    # може знадобитись викликаючій стороні (наприклад для майбутнього PID наведення)
    dx, dy, z_percent = compute_offset_and_scale(frame, bbox)

    h_frame, w_frame = frame.shape[:2]
    center = (w_frame // 2, h_frame // 2)
    x, y, w, h = bbox
    target_point = (int(x + w / 2), int(y + h / 2))

    cv2.line(frame, center, target_point, COLOR_LOCK, 2)
    cv2.circle(frame, center, 4, COLOR_LOCK, -1)
    cv2.putText(frame, f"dx={dx:.0f}px dy={dy:.0f}px",
                (target_point[0] + 10, max(0, target_point[1] - 10)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_LOCK, 2)

    return dx, dy, z_percent

class FireController:
    def __init__(self):
        self.locked_id = None                 # id захопленого TrackedObject
        self._pre_fire_landing_enabled = None
        self._locked_class_name = ""
        self._locked_confidence = None
        self._last_seen_bbox = None           # bbox на останньому кадрі знайденої цілі
        self._last_seen_time = None           # video_time кадру, від якого рахується допустимий період очікування на знаходження втраченої цілі
        self.pre_fire_power_save_enabled = None

    def activate(self, tracked_objects, frame=None, frame_idx=None, video_time=None):
        if self.locked_id is not None:
            return
        if not tracked_objects:
            return

        best = max(tracked_objects, key=lambda o: o.confidence)
        self.locked_id = best.id
        self._locked_class_name = best.class_name
        self._locked_confidence = best.confidence
        self._last_seen_bbox = best.bbox
        self._last_seen_time = video_time

        print(f"[FIRE] LOCK ID {best.id} ({best.class_name}, conf={best.confidence:.2f})")

        if frame is not None:
            log_event(frame, best.bbox, "TARGET_LOCKED", frame_idx, video_time,
                       object_id=best.id, class_name=best.class_name,
                       confidence=best.confidence, take_screenshot=True)

    def process_frame(self, frame, tracked_objects, frame_idx, video_time):
        if self.locked_id is None:
            return False

        locked_obj = next((o for o in tracked_objects if o.id == self.locked_id), None)

        if locked_obj is None:
            missing_for = video_time - self._last_seen_time
            if missing_for <= FIRE_LOCK_LOST_GRACE_SEC:
                draw_locked_target(frame, self._last_seen_bbox, self._locked_class_name, self._locked_confidence)
                calculate_and_draw_offset(frame, self._last_seen_bbox)
                return True

            # допустимий період очікування вийшов - ціль втрачена
            log_event(frame, None, "TARGET_LOST", frame_idx, video_time,
                       object_id=self.locked_id, class_name=self._locked_class_name,
                       confidence=self._locked_confidence, take_screenshot=True)
            print(f"[FIRE] TARGET_LOST (ID {self.locked_id}) - повернення до штатної роботи")

            self.locked_id = None
            self._locked_class_name = ""
            self._locked_confidence = None
            self._last_seen_bbox = None
            self._last_seen_time = None

            return False

        # останній відомий стан для випадку тимчасового зникнення цілі
        self._locked_class_name = locked_obj.class_name
        self._locked_confidence = locked_obj.confidence
        self._last_seen_bbox = locked_obj.bbox
        self._last_seen_time = video_time

        draw_locked_target(frame, locked_obj.bbox, locked_obj.class_name, locked_obj.confidence)
        calculate_and_draw_offset(frame, locked_obj.bbox)
        return True