import os
from datetime import datetime
import cv2
from config import (
    TEMP_WARNING_MIN_C,
    TEMP_CRITICAL_C,
    WARNING_YOLO_PAUSE_SEC,
    SCREENSHOT_DIR,
    COLOR_WARNING,
    COLOR_CRITICAL,
)
from logger import log_event

class ThermalDecision:
    # можливі action:
    NONE = "none"
    PAUSE = "pause"
    RESUME = "resume"
    DISABLE_PERMANENT = "disable_permanent"
    DISABLE_PERMANENT_RTH = "disable_permanent_rth"

    def __init__(self, level, action, take_screenshot=False):
        self.level = level # None | "WARNING" | "CRITICAL"
        self.action = action
        self.take_screenshot = take_screenshot

    def __repr__(self):
        return (f"ThermalDecision(level={self.level!r}, action={self.action!r}, "
                f"take_screenshot={self.take_screenshot})")

class ThermalController:
    def __init__(self):
        self.yolo_enabled = True
        self.video_processing_enabled = True 
        self.pending_final_screenshot = False 

        self._warning_cooldown_until = None 
        self._yolo_off_permanent = False
        self._critical_handled = False
        self._last_temp_c = None

    def evaluate(self, temp_c, frame, frame_idx, video_time, rth_active=False):
        # за відсутності окремого RTH-стану, за замовчуванням False.
        self._last_temp_c = temp_c

        if temp_c > TEMP_CRITICAL_C:
            log_event(frame, None, "CRITICAL", frame_idx, video_time,
                       class_name=f"chip_temp_c={temp_c:.1f}", take_screenshot=False)
            if self._critical_handled:
                return ThermalDecision("CRITICAL", ThermalDecision.NONE)
            return ThermalDecision("CRITICAL", ThermalDecision.DISABLE_PERMANENT_RTH, take_screenshot=True)

        if temp_c >= TEMP_WARNING_MIN_C:
            log_event(frame, None, "WARNING", frame_idx, video_time,
                       class_name=f"chip_temp_c={temp_c:.1f}", take_screenshot=False)

            if rth_active:
                if self._yolo_off_permanent:
                    return ThermalDecision("WARNING", ThermalDecision.NONE)
                return ThermalDecision("WARNING", ThermalDecision.DISABLE_PERMANENT)
            if self._yolo_off_permanent:
                return ThermalDecision("WARNING", ThermalDecision.NONE)            
            if self._warning_cooldown_until is None:
                return ThermalDecision("WARNING", ThermalDecision.PAUSE)
            if video_time >= self._warning_cooldown_until:
                return ThermalDecision("WARNING", ThermalDecision.DISABLE_PERMANENT_RTH)

            return ThermalDecision("WARNING", ThermalDecision.NONE)

        if self._warning_cooldown_until is not None and not self._yolo_off_permanent:
            return ThermalDecision(None, ThermalDecision.RESUME)
        return ThermalDecision(None, ThermalDecision.NONE)

    def commit(self, decision, video_time):
        action = decision.action

        if action == ThermalDecision.NONE:
            return

        if action == ThermalDecision.PAUSE:
            self._warning_cooldown_until = video_time + WARNING_YOLO_PAUSE_SEC
            self.yolo_enabled = False
            self.video_processing_enabled = False
            print(f"[thermal] YOLO і трекер призупинено на {WARNING_YOLO_PAUSE_SEC:.0f} сек")
            return

        if action == ThermalDecision.RESUME:
            self._warning_cooldown_until = None
            self.yolo_enabled = True
            self.video_processing_enabled = True
            print("[thermal] температура ок — вмикається YOLO і трекер")
            return

        if action == ThermalDecision.DISABLE_PERMANENT:
            self._yolo_off_permanent = True
            self.yolo_enabled = False
            self.video_processing_enabled = False
            print("[thermal] YOLO і трекер вимкнено")
            return

        if action == ThermalDecision.DISABLE_PERMANENT_RTH:
            if decision.level == "CRITICAL":
                self._critical_handled = True
            self._yolo_off_permanent = True
            self.yolo_enabled = False
            self.video_processing_enabled = False
            if decision.take_screenshot:
                self.pending_final_screenshot = True
            print(f"[thermal] {decision.level}: YOLO і трекер вимкнено")
            return

    def save_final_screenshot(self, frame):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        path = os.path.join(SCREENSHOT_DIR, f"CRITICAL_{ts_str}.jpg")
        cv2.imwrite(path, frame)
        self.pending_final_screenshot = False

    def banner_lines(self):
        if self._critical_handled:
            temp_txt = f"{self._last_temp_c:.0f}C" if self._last_temp_c is not None else "?"
            return ["CRITICAL: CHIP OVERHEAT " + temp_txt, "VIDEO PROCESSING HALTED — RETURNING TO STATION"]
        if self._last_temp_c is not None and self._last_temp_c >= TEMP_WARNING_MIN_C:
            return [f"WARNING: CHIP TEMPERATURE {self._last_temp_c:.0f}C"]
        return None

    def banner_color(self):
        return COLOR_CRITICAL if self._critical_handled else COLOR_WARNING