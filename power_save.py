from config import DETECT_INTERVAL, POWER_SAVE_DETECT_INTERVAL
from logger import log_event

class PowerSaveController:
    def __init__(self):
        self.enabled = False

    def active_detect_interval(self):
        return POWER_SAVE_DETECT_INTERVAL if self.enabled else DETECT_INTERVAL

    def toggle(self, frame, frame_idx, video_time):
        self.enabled = not self.enabled
        interval = self.active_detect_interval()
        print(f"[power save] {'ON' if self.enabled else 'OFF'} (detect_interval={interval})")
        log_event(
            frame, 
            None,
            "POWER_SAVE_MODE_ON" if self.enabled else "POWER_SAVE_MODE_OFF",
            frame_idx, 
            video_time,
            None, 
            class_name=f"detect_interval={interval}",
            confidence=None,
            take_screenshot=False,
        )