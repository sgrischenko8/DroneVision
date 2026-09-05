import queue
import random
import threading
import time
from config import (
    TELEMETRY_CHECK_INTERVAL_SEC,
    TELEMETRY_BATTERY_START_PERCENT,
    TELEMETRY_BATTERY_DRAIN_PERCENT_PER_SEC,
    TELEMETRY_LOW_BATTERY_THRESHOLD_PERCENT,
    TELEMETRY_CHIP_TEMP_NOMINAL_C,
    TELEMETRY_CHIP_TEMP_SPIKE_CHANCE_PER_CHECK,
    TELEMETRY_CHIP_TEMP_ESCALATE_CHANCE_PER_CHECK,
    TELEMETRY_CHIP_TEMP_WARNING_RANGE,
    TELEMETRY_CHIP_TEMP_CRITICAL_RANGE,
)

class DroneTelemetry:
    def __init__(self):
        self._queue = queue.Queue()
        self._battery_percent = TELEMETRY_BATTERY_START_PERCENT
        self._low_battery_fired = False   
        self._chip_temp_state = "NOMINAL"
        self._stop_flag = threading.Event()
        self._thread = threading.Thread(target=self._telemetry_loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_flag.set()

    def poll_events(self):
        events = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    def _telemetry_loop(self):
        last_tick = time.monotonic()
        while not self._stop_flag.is_set():
            time.sleep(TELEMETRY_CHECK_INTERVAL_SEC)
            now = time.monotonic()
            elapsed = now - last_tick
            last_tick = now

            # симуляція розряду батареї
            self._battery_percent = max(
                0.0, self._battery_percent - TELEMETRY_BATTERY_DRAIN_PERCENT_PER_SEC * elapsed
            )
            if (not self._low_battery_fired
                    and self._battery_percent <= TELEMETRY_LOW_BATTERY_THRESHOLD_PERCENT):
                self._low_battery_fired = True
                self._queue.put({
                    "event": "LOW_BATTERY",
                    "battery_percent": round(self._battery_percent, 1),
                })

            self._queue.put({
                "event": "BATTERY_LEVEL",
                "battery_percent": round(self._battery_percent, 1),
            })

            if self._chip_temp_state == "NOMINAL":
                temp_c = TELEMETRY_CHIP_TEMP_NOMINAL_C + random.uniform(-2.0, 2.0)
                if random.random() < TELEMETRY_CHIP_TEMP_SPIKE_CHANCE_PER_CHECK:
                    self._chip_temp_state = "WARNING"
            elif self._chip_temp_state == "WARNING":
                temp_c = random.uniform(*TELEMETRY_CHIP_TEMP_WARNING_RANGE)
                if random.random() < TELEMETRY_CHIP_TEMP_ESCALATE_CHANCE_PER_CHECK:
                    self._chip_temp_state = "CRITICAL"
            else:
                temp_c = random.uniform(*TELEMETRY_CHIP_TEMP_CRITICAL_RANGE)

            self._queue.put({"event": "CHIP_TEMP", "temp_c": round(temp_c, 1)})